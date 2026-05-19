# Photonome Workers

Three long-running Python processes that consume Google Cloud Pub/Sub messages, run GPU jobs on the DGX Spark (128 GB unified memory), upload results to Firebase Storage, and publish completion messages back to Pub/Sub.

**No FastAPI / no HTTP** — every trigger is a Pub/Sub message. Pull subscribers handle the long-running case (LoRA training easily exceeds Pub/Sub push's 10-min ack ceiling); the `google-cloud-pubsub` library auto-extends the ack deadline while the lease is held.

## Workers

| Worker | Model | Purpose |
|---|---|---|
| `edit_worker.py` | `black-forest-labs/FLUX.1-Kontext-dev` | Edits a user-uploaded image with a style LoRA (e.g. `Shakker-Labs/FLUX.1-Kontext-dev-LoRA-Flat-Cartoon-Style`). Hot-swaps LoRAs per request via the PEFT adapter API — base model stays resident. |
| `train_worker.py` | `black-forest-labs/FLUX.2-dev` via `ostris/ai-toolkit` | Trains a personal LoRA from 8–10 user selfies. Holds a VRAM-exclusive lock; uploads `.safetensors` to `loras/{userId}.safetensors`. |
| `generate_worker.py` | `black-forest-labs/FLUX.2-dev` | Generates an image from a prompt + the user's trained LoRA. Yields VRAM (unloads its pipeline) when `train_worker` signals it wants the GPU. |

## Layout

```
workers/
  pyproject.toml
  requirements.txt
  Makefile
  core/                       # shared modules
    config.py firebase.py pubsub.py completion.py
    vram_lock.py styles.py logging.py
    models/
      edit_pipeline.py generate_pipeline.py training.py
  edit_worker.py train_worker.py generate_worker.py
  scripts/smoke_local.py      # offline message replay
```

## Setup

Use a dedicated virtualenv for the workers — they pull in heavy GPU deps (torch, diffusers from git, transformers, accelerate, peft) that shouldn't pollute the system Python.

```bash
# 1. workers venv
cd workers
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .

# 2. ai-toolkit (separate install, separate venv — invoked by train_worker via subprocess)
git clone https://github.com/ostris/ai-toolkit /opt/ai-toolkit
cd /opt/ai-toolkit
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
deactivate
```

`train_worker` shells out to ai-toolkit via `subprocess.run([sys.executable, ...])` using the *workers* venv's interpreter by default. If ai-toolkit's deps conflict with the workers venv, point `train_worker` at ai-toolkit's interpreter by overriding `sys.executable` — set `AI_TOOLKIT_PYTHON` env var and update `core/models/training.py` to use it. Simplest path: share one venv if the deps are compatible.

Activate the workers venv before running any worker:

```bash
cd workers && source .venv/bin/activate
make edit          # or: python edit_worker.py
```

The `.venv/` directory is already gitignored (see root `.gitignore` Python section).

Environment variables (all optional; defaults in `core/config.py`):
- `PHOTONOME_GCP_PROJECT` (default: `photonome`)
- `PHOTONOME_FIREBASE_CREDENTIALS` — service account JSON path
- `PHOTONOME_FIREBASE_STORAGE_BUCKET`
- `PHOTONOME_EDIT_SUBSCRIPTION`, `PHOTONOME_TRAIN_SUBSCRIPTION`, `PHOTONOME_GENERATE_SUBSCRIPTION`
- `PHOTONOME_COMPLETIONS_TOPIC`
- `PHOTONOME_AI_TOOLKIT_DIR` (default: `/opt/ai-toolkit`)
- `HF_TOKEN` — needed if the FLUX checkpoints are gated for your account

## Provision Pub/Sub (one-time)

```bash
PROJECT=photonome
for t in edit-jobs train-jobs generate-jobs job-completions \
         edit-jobs-dlq train-jobs-dlq generate-jobs-dlq; do
  gcloud pubsub topics create $t --project=$PROJECT
done

for name in edit train generate; do
  gcloud pubsub subscriptions create ${name}-jobs-sub \
    --topic=${name}-jobs \
    --ack-deadline=600 \
    --message-retention-duration=7d \
    --enable-exactly-once-delivery \
    --dead-letter-topic=${name}-jobs-dlq \
    --max-delivery-attempts=5 \
    --project=$PROJECT
done
```

The completion subscriber lives in `functions/` (Firebase Function that sends FCM).

## Run

```bash
make edit       # python edit_worker.py
make train      # python train_worker.py
make generate   # python generate_worker.py
```

### tmux session (recommended)

Run all three workers in a named tmux session with one window each:

```bash
# Create session with 3 windows
tmux new-session -d -s photonome -n train

# Train worker
tmux send-keys -t photonome:train "cd /home/kemal/Projects/photonome_new/workers && source .venv/bin/activate && make train" Enter

# Edit worker
tmux new-window -t photonome -n edit
tmux send-keys -t photonome:edit "cd /home/kemal/Projects/photonome_new/workers && source .venv/bin/activate && make edit" Enter

# Generate worker
tmux new-window -t photonome -n generate
tmux send-keys -t photonome:generate "cd /home/kemal/Projects/photonome_new/workers && source .venv/bin/activate && make generate" Enter

# Attach
tmux attach -t photonome
```

Switch between windows with `Ctrl+b 0/1/2` or by name: `Ctrl+b w`.

Each worker:
1. Loads its model into VRAM at startup (only `train_worker` skips this — ai-toolkit loads its own).
2. Opens a streaming pull subscription with `max_messages=1` and a long lease (2 h for edit/generate, 4 h for train).
3. On each message: downloads inputs from Storage, runs the GPU job, uploads the result, publishes a completion message, acks.
4. On exception: publishes a failure completion message and nacks (redelivery up to 5 attempts, then dead-letter).

## Message schemas

**`edit-jobs`**:
```json
{ "userId": "u1", "jobId": "j1", "inputImagePath": "uploads/u1/raw.jpg",
  "style": "flat-cartoon", "prompt": "make her smile", "guidanceScale": 2.5 }
```

**`train-jobs`**:
```json
{ "userId": "u1", "jobId": "t1",
  "imagePaths": ["selfies/u1/01.jpg", "selfies/u1/02.jpg", "..."],
  "steps": 1000 }
```

**`generate-jobs`**:
```json
{ "userId": "u1", "jobId": "g1", "prompt": "TOK as an astronaut, cinematic",
  "loraPath": "loras/u1.safetensors", "steps": 28, "width": 1024, "height": 1024 }
```
`loraPath` defaults to `loras/{userId}.safetensors`.

**`job-completions`** (every worker publishes the same shape):
```json
{ "userId": "u1", "jobId": "j1", "kind": "edit|train|generate",
  "status": "success|error", "outputPath": "outputs/u1/j1.png", "error": null }
```

## VRAM mutex (train vs generate)

`train_worker` and `generate_worker` cooperate via two files in `/var/run/photonome/`:

- `vram.lock` — advisory `fcntl.flock`. `generate` holds `LOCK_SH`; `train` takes `LOCK_EX`.
- `train.want` — `train` touches this when it wants the GPU; `generate` polls every 1 s and yields when it appears.

When `generate` is mid-inference and observes `train.want`, its `callback_on_step_end` raises `YieldRequested`. The handler unloads the pipeline (CPU + `torch.cuda.empty_cache()`), releases the shared lock, and nacks the message — Pub/Sub redelivers it after training completes and the lock is released.

## Verify end-to-end

```bash
# 1. Publish a fake job (substitute real paths in your Storage bucket)
gcloud pubsub topics publish edit-jobs --message='{"userId":"u1","jobId":"j1","inputImagePath":"test/in.jpg","style":"flat-cartoon","prompt":"smiling"}'

# 2. Read completions
gcloud pubsub subscriptions create job-completions-debug --topic=job-completions
gcloud pubsub subscriptions pull job-completions-debug --auto-ack --limit=5
```

Offline (no Pub/Sub, no Firebase publish):
```bash
echo '{"userId":"u1","jobId":"j1","inputImagePath":"test/in.jpg","style":"flat-cartoon","prompt":"smiling"}' > tests/edit.json
make smoke-edit
```

## Troubleshooting

### `ERROR: No matching distribution found for torchcodec==0.9.1`

Hit while installing ai-toolkit's requirements on aarch64 / Python 3.12 (DGX Spark). `torchcodec==0.9.1` has no aarch64+cp312 wheel — only `0.11.x` is published. torchcodec is for video/audio decoding and isn't on the LoRA training path, so a version bump is safe.

ai-toolkit splits its deps across `requirements.txt` and `requirements_base.txt` (and possibly more), so patch all of them:

```bash
find /opt/ai-toolkit -maxdepth 2 -name 'requirements*.txt' -exec sed -i 's/torchcodec==0.9.1/torchcodec==0.11.1/g' {} +
pip install -r /opt/ai-toolkit/requirements.txt
```

Or drop the pin entirely and let pip pick whatever is available:

```bash
find /opt/ai-toolkit -maxdepth 2 -name 'requirements*.txt' -exec sed -i 's/^torchcodec==.*$/torchcodec/' {} +
pip install -r /opt/ai-toolkit/requirements.txt
```
