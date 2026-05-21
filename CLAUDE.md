# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Photonome is an AI photo generation platform with three components:

1. **`web/`** — Vite + React + TypeScript + Tailwind v4 SPA. Lets users submit GPU jobs and observe results live.
2. **`functions/`** — Firebase Cloud Functions (Node.js). Handles job submission (writes to Firestore, publishes to Pub/Sub) and job completion events (updates Firestore doc with signed URL).
3. **`workers/`** — Python GPU workers running on a DGX Spark (128 GB unified memory). Pull from Pub/Sub, run diffusers inference or LoRA training, publish completion messages.
4. **`comfyui_workflows/`** — JSON ComfyUI API workflow files (alternative inference path, not used by workers currently).

## Data Flow

```
Web SPA → httpsCallable → Firebase Function → Pub/Sub topic
                                            → Firestore /jobs/{jobId} (status: queued)

Pub/Sub → Worker → Firebase Storage (output) → Pub/Sub job-completions
                                             → Firebase Function (onJobCompletion)
                                             → Firestore /jobs/{jobId} (status + outputUrl)
                                             → Web SPA (onSnapshot live update)
```

## Commands

### Web (`web/`)

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # tsc -b && vite build → dist/
npm run lint
npm run preview
```

Firebase config comes from `.env` (never committed). Required vars: `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_STORAGE_BUCKET`, `VITE_FIREBASE_MESSAGING_SENDER_ID`, `VITE_FIREBASE_APP_ID`, `VITE_FIREBASE_MEASUREMENT_ID`, `VITE_FIREBASE_FUNCTIONS_REGION` (set to `europe-west3`).

### Functions (`functions/`)

```bash
npm run lint
npm run deploy     # firebase deploy --only functions
npm run serve      # firebase emulators:start --only functions
npm run logs       # firebase functions:log
```

### Workers (`workers/`)

```bash
# One-time setup
cd workers && python3 -m venv .venv && source .venv/bin/activate && pip install -e .

# Run workers (activate venv first)
make edit          # python edit_worker.py
make train         # python train_worker.py
make generate      # python generate_worker.py

# Smoke tests (offline, no Pub/Sub)
make smoke-edit    # replays tests/edit.json
make smoke-train
make smoke-generate
```

Recommended: run all three in a tmux session (`workers/README.md` has the full tmux setup).

Worker settings are controlled via `PHOTONOME_*` env vars or a `.env` file; see `core/config.py` for all knobs (`PHOTONOME_GCP_PROJECT`, `PHOTONOME_FIREBASE_CREDENTIALS`, `PHOTONOME_FIREBASE_STORAGE_BUCKET`, etc.).

**ai-toolkit** (used only by `train_worker`) must be installed separately in `/opt/ai-toolkit` with its own venv. See `workers/README.md`.

## Architecture Details

### Workers (`workers/`)

- Each worker pulls one message at a time (`max_messages=1`) with a long lease (2–4 h) so it survives LoRA training without redelivery.
- `core/pubsub.py` — `run_subscriber()` drives the subscriber loop; handlers call `message.ack()` on success and `message.nack()` on failure (Pub/Sub redelivers, max 5 attempts, then dead-letter queue).
- `core/completion.py` — `publish_completion()` is called by every worker to signal the Firebase function.
- `core/config.py` — pydantic-settings `Settings`; singleton via `@lru_cache get_settings()`.
- `core/vram_lock.py` — cooperative VRAM mutex between `train_worker` (exclusive) and `generate_worker` (shared). Uses `fcntl.flock` on a file plus a `train.want` sentinel that `generate_worker` polls every 1 s. When `generate_worker` sees the sentinel mid-inference, its `callback_on_step_end` raises `YieldRequested`; the handler unloads the pipeline and nacks so Pub/Sub redelivers after training finishes.
- `core/styles.py` — maps style slug (e.g. `"flat-cartoon"`) to HuggingFace LoRA repo + scale.
- `core/models/edit_pipeline.py` — loads `FluxKontextPipeline`, hot-swaps LoRAs per request via PEFT adapter API (base model stays in VRAM).
- `train_worker` shells out to ai-toolkit via `subprocess.run` rather than importing it directly to avoid dependency conflicts.

### Functions (`functions/index.js`)

Single file with four exports:
- `submitEditJob`, `submitTrainJob`, `submitGenerateJob` — HTTPS callables; require Firebase Auth; write to `jobs/{jobId}` and publish to Pub/Sub.
- `onJobCompletion` — Pub/Sub trigger on `job-completions`; updates Firestore; generates a 7-day signed URL (falls back to a download-token URL if signing fails).

All functions are deployed to `europe-west3`.

### Web (`web/src/`)

- `firebase.ts` — initializes Firebase SDK from env vars; exports `auth`, `db`, `storage`, `functions`.
- `useAuth.ts` — anonymous sign-in hook.
- `jobs.ts` — exports callable wrappers (`submitEditJob` etc.) and `useJobs()` hook (Firestore `onSnapshot` query on `/jobs` ordered by `createdAt desc`).
- `types.ts` — shared TypeScript types: `JobDoc`, `JobKind`, `JobStatus`, and per-job param types.
- Pages (`pages/`) call the submit callables and upload images to Storage before calling the function.
- `components/JobList.tsx` — renders live job list using results from `useJobs()`.

### Firebase / GCP

- Project: `photonome`, region: `europe-west3`
- Firestore: `/jobs/{jobId}` — single collection, all job kinds.
- Storage: `uploads/`, `selfies/`, `loras/`, `outputs/` prefixes (enforced by convention, not rules).
- Pub/Sub topics: `edit-jobs`, `train-jobs`, `generate-jobs`, `job-completions` + `-dlq` variants.
- Auth: anonymous only (tighten before production).
- Firestore + Storage rules currently allow any authenticated user.
- Hosting: `web/dist` → `photonome-test` Firebase Hosting site.

## Known Issues / Gotchas

- **`torchcodec` on aarch64/cp312**: ai-toolkit pins `torchcodec==0.9.1` which has no wheel for DGX Spark. Patch with `sed -i 's/torchcodec==0.9.1/torchcodec==0.11.1/g'` across all ai-toolkit `requirements*.txt` files.
- **VRAM mutex lock files** live in `~/.cache/photonome/run/` (controlled by `settings.vram_lock_dir`). If a worker crashes mid-job, the `train.want` sentinel may be left behind — delete it manually before restarting.
- **Firebase Admin credentials**: `core/config.py` defaults `firebase_credentials` to the absolute path of the service account JSON in the repo root. Override via `PHOTONOME_FIREBASE_CREDENTIALS` if moving the file.
- **Model IDs**: `edit_worker` uses `FLUX.1-Kontext-dev`; `train_worker` and `generate_worker` use `FLUX.1-dev` (config key `flux2_model_id`).
