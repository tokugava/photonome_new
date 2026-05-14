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

```bash
# 1. system deps for ai-toolkit (separate install)
git clone https://github.com/ostris/ai-toolkit /opt/ai-toolkit
cd /opt/ai-toolkit && pip install -r requirements.txt

# 2. worker deps
cd workers
pip install -e .
```

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
