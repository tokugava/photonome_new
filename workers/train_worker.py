from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from core import firebase
from core.completion import publish_completion
from core.config import get_settings
from core.logging import setup
from core.models import training
from core.pubsub import run_subscriber
from core.vram_lock import TrainLock

log = setup("train_worker")


def _handle(msg: dict, message) -> None:
    settings = get_settings()
    user_id = msg["userId"]
    job_id = msg["jobId"]
    image_paths: list[str] = msg["imagePaths"]
    steps = int(msg.get("steps", 1000))
    log_ctx = log.bind(user_id=user_id, job_id=job_id, kind="train")

    workdir = settings.work_dir / f"train-{user_id}-{uuid.uuid4().hex[:6]}"
    images_dir = workdir / "images"
    output_dir = workdir / "output"
    images_dir.mkdir(parents=True, exist_ok=True)

    try:
        log_ctx.info("downloading_selfies", count=len(image_paths))
        for i, gs in enumerate(image_paths):
            suffix = Path(gs).suffix or ".jpg"
            firebase.download(gs, images_dir / f"{i:03d}{suffix}")
        training.ensure_captions(images_dir)

        cfg = training.write_yaml(
            name=user_id,
            images_dir=images_dir,
            output_dir=output_dir,
            steps=steps,
        )

        with TrainLock():
            log_ctx.info("training_started", steps=steps)
            training.run_aitoolkit(cfg)

        safetensors = training.expected_output(user_id, output_dir)
        if not safetensors.exists():
            raise FileNotFoundError(f"expected LoRA not found at {safetensors}")
        output_path = f"loras/{user_id}.safetensors"
        firebase.upload(safetensors, output_path, content_type="application/octet-stream")

        publish_completion(
            user_id=user_id, job_id=job_id, kind="train",
            status="success", output_path=output_path,
        )
        log_ctx.info("train_succeeded", output=output_path)
    except Exception as exc:
        log_ctx.exception("train_failed", error=str(exc))
        publish_completion(
            user_id=user_id, job_id=job_id, kind="train",
            status="error", error=str(exc),
        )
        raise
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main() -> None:
    settings = get_settings()
    firebase.init_app()
    run_subscriber(settings.train_subscription, _handle, lease_hours=settings.train_lease_hours)


if __name__ == "__main__":
    main()
