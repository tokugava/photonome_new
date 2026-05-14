from __future__ import annotations

import uuid
from pathlib import Path

from core import firebase
from core.completion import publish_completion
from core.config import get_settings
from core.logging import setup
from core.models import generate_pipeline
from core.pubsub import run_subscriber
from core.vram_lock import GenerateGuard, YieldRequested

log = setup("generate_worker")


def _cache_lora(user_id: str, lora_path: str | None) -> Path:
    settings = get_settings()
    storage_path = lora_path or f"loras/{user_id}.safetensors"
    local = settings.lora_cache_dir / Path(storage_path).name
    if not local.exists():
        log.info("fetching_lora", path=storage_path)
        firebase.download(storage_path, local)
    return local


class _State:
    pipe = None


def _handle_factory(settings, guard: GenerateGuard, state: _State):
    def builder():
        return generate_pipeline.build(settings.flux2_model_id)

    def handle(msg: dict, message) -> None:
        user_id = msg["userId"]
        job_id = msg["jobId"]
        log_ctx = log.bind(user_id=user_id, job_id=job_id, kind="generate")

        state.pipe = guard.ensure_loaded(state.pipe, builder)
        local_lora = _cache_lora(user_id, msg.get("loraPath"))
        adapter_name = generate_pipeline.apply_user_lora(state.pipe, local_lora, scale=msg.get("loraScale", 1.0))

        workdir = settings.work_dir / f"gen-{job_id}-{uuid.uuid4().hex[:6]}"
        workdir.mkdir(parents=True, exist_ok=True)
        yielded = False
        try:
            log_ctx.info("running_inference", prompt=msg["prompt"][:120])
            result = state.pipe(
                prompt=msg["prompt"],
                num_inference_steps=int(msg.get("steps", 28)),
                guidance_scale=msg.get("guidanceScale", 3.5),
                width=int(msg.get("width", 1024)),
                height=int(msg.get("height", 1024)),
                callback_on_step_end=guard.step_callback,
            ).images[0]
            output_local = workdir / "output.png"
            result.save(output_local, format="PNG")
            output_path = f"outputs/{user_id}/{job_id}.png"
            firebase.upload(output_local, output_path, content_type="image/png")
            publish_completion(
                user_id=user_id, job_id=job_id, kind="generate",
                status="success", output_path=output_path,
            )
            log_ctx.info("generate_succeeded", output=output_path)
        except YieldRequested:
            log_ctx.info("yielding_mid_inference")
            yielded = True
            guard.yield_vram(state.pipe)
            state.pipe = None
            raise  # pubsub.py nacks -> redelivery after train finishes
        except Exception as exc:
            log_ctx.exception("generate_failed", error=str(exc))
            publish_completion(
                user_id=user_id, job_id=job_id, kind="generate",
                status="error", error=str(exc),
            )
            raise
        finally:
            if not yielded and state.pipe is not None:
                generate_pipeline.clear_user_lora(state.pipe, adapter_name)

    return handle


def main() -> None:
    settings = get_settings()
    firebase.init_app()
    guard = GenerateGuard()
    state = _State()
    handle = _handle_factory(settings, guard, state)
    run_subscriber(settings.generate_subscription, handle, lease_hours=settings.inference_lease_hours)


if __name__ == "__main__":
    main()
