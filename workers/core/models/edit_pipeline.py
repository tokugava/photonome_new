from __future__ import annotations

import structlog
import torch
from diffusers import FluxKontextPipeline

from core.styles import resolve

log = structlog.get_logger(__name__)


def build(model_id: str) -> FluxKontextPipeline:
    log.info("loading_flux_kontext", model=model_id)
    pipe = FluxKontextPipeline.from_pretrained(model_id, torch_dtype=torch.bfloat16)
    pipe.to("cuda")
    return pipe


def apply_style(pipe: FluxKontextPipeline, style: str) -> tuple[str, float]:
    repo, weight_name, scale = resolve(style)
    adapter_name = style.replace("/", "_").replace(" ", "_")
    loaded = set(getattr(pipe, "peft_config", {}) or {})
    if adapter_name not in loaded:
        log.info("loading_lora", repo=repo, weight=weight_name, adapter=adapter_name)
        kwargs: dict = {"adapter_name": adapter_name}
        if weight_name:
            kwargs["weight_name"] = weight_name
        pipe.load_lora_weights(repo, **kwargs)
    pipe.set_adapters([adapter_name], adapter_weights=[scale])
    return adapter_name, scale


def reset_style(pipe: FluxKontextPipeline, adapter_name: str) -> None:
    try:
        pipe.delete_adapters([adapter_name])
    except Exception as exc:
        log.warning("delete_adapter_failed", adapter=adapter_name, error=str(exc))
