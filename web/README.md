# Photonome web

Minimal Vite + React + TypeScript + Tailwind v4 SPA for triggering and observing the GPU workers in `../workers/`.

## What it does

1. Signs you in anonymously to Firebase.
2. Three tabs — **Edit** / **Train LoRA** / **Generate** — upload images to Firebase Storage and call an HTTPS callable function (in `../functions/`) that publishes a Pub/Sub message to the matching topic (`edit-jobs`, `train-jobs`, `generate-jobs`).
3. The callable also writes a Firestore doc at `/jobs/{jobId}` with `status: "queued"`.
4. When a worker finishes, it publishes to `job-completions`; the `onJobCompletion` function in `../functions/` updates the Firestore doc with `status` and a signed `outputUrl`.
5. The SPA subscribes via `onSnapshot` and renders status + result image live.

## Develop

```bash
npm install
npm run dev    # http://localhost:5173
```

## Build

```bash
npm run build  # tsc -b && vite build → dist/
npm run preview
```

## Required Firebase setup

- Anonymous auth enabled (Authentication → Sign-in method → Anonymous → Enable).
- Functions deployed from `../functions/` to `europe-west3` (matches `getFunctions(app, "europe-west3")` in `src/firebase.ts` and `setGlobalOptions({ region: "europe-west3" })` in `functions/index.js`).
- Pub/Sub topics provisioned per `../workers/README.md`.
- Workers running and consuming from their subscriptions.

## Notes

- The Firebase config in `src/firebase.ts` is committed because it's public web-SDK config (project ID, app ID, API key). Access control is enforced via Firebase Auth + Firestore/Storage rules, not by hiding the config.
- Storage and Firestore rules currently require any authenticated user; tighten before going beyond local testing.
