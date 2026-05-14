from __future__ import annotations

from pathlib import Path

import structlog
import torch
from diffusers import DiffusionPipeline

log = structlog.get_logger(__name__)


def build(model_id: str) -> DiffusionPipeline:
    log.info("loading_flux2", model=model_id)
    pipe = DiffusionPipeline.from_pretrained(model_id, torch_dtype=torch.bfloat16)
    pipe.to("cuda")
    return pipe


def apply_user_lora(pipe: DiffusionPipeline, lora_path: Path, scale: float = 1.0) -> str:
    adapter_name = "user"
    log.info("loading_user_lora", path=str(lora_path), adapter=adapter_name)
    pipe.load_lora_weights(str(lora_path), adapter_name=adapter_name)
    pipe.set_adapters([adapter_name], adapter_weights=[scale])
    return adapter_name


def clear_user_lora(pipe: DiffusionPipeline, adapter_name: str = "user") -> None:
    try:
        pipe.delete_adapters([adapter_name])
    except Exception as exc:
        log.warning("delete_user_lora_failed", adapter=adapter_name, error=str(exc))
