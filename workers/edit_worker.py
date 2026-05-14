from __future__ import annotations

import uuid

from PIL import Image

from core import firebase
from core.completion import publish_completion
from core.config import get_settings
from core.logging import setup
from core.models import edit_pipeline
from core.pubsub import run_subscriber

log = setup("edit_worker")


def _handle_factory(settings, pipe):
    def handle(msg: dict, message) -> None:
        user_id = msg["userId"]
        job_id = msg["jobId"]
        log_ctx = log.bind(user_id=user_id, job_id=job_id, kind="edit")

        workdir = settings.work_dir / f"edit-{job_id}-{uuid.uuid4().hex[:6]}"
        workdir.mkdir(parents=True, exist_ok=True)
        try:
            src = firebase.download(msg["inputImagePath"], workdir / "input.png")
            adapter_name, _ = edit_pipeline.apply_style(pipe, msg["style"])
            try:
                log_ctx.info("running_inference", style=msg["style"])
                result = pipe(
                    image=Image.open(src).convert("RGB"),
                    prompt=msg.get("prompt", ""),
                    guidance_scale=msg.get("guidanceScale", 2.5),
                ).images[0]
                output_local = workdir / "output.png"
                result.save(output_local, format="PNG")
                output_path = f"outputs/{user_id}/{job_id}.png"
                firebase.upload(output_local, output_path, content_type="image/png")
            finally:
                edit_pipeline.reset_style(pipe, adapter_name)
            publish_completion(
                user_id=user_id, job_id=job_id, kind="edit",
                status="success", output_path=output_path,
            )
            log_ctx.info("edit_succeeded", output=output_path)
        except Exception as exc:
            log_ctx.exception("edit_failed", error=str(exc))
            publish_completion(
                user_id=user_id, job_id=job_id, kind="edit",
                status="error", error=str(exc),
            )
            raise

    return handle


def main() -> None:
    settings = get_settings()
    firebase.init_app()
    pipe = edit_pipeline.build(settings.flux_kontext_model_id)
    handle = _handle_factory(settings, pipe)
    run_subscriber(settings.edit_subscription, handle, lease_hours=settings.inference_lease_hours)


if __name__ == "__main__":
    main()
