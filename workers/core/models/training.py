from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import structlog

from core.config import get_settings

log = structlog.get_logger(__name__)

TRIGGER_WORD = "TOK"
DEFAULT_CAPTION = f"a photo of {TRIGGER_WORD}"


def ensure_captions(images_dir: Path) -> None:
    for img in sorted(images_dir.iterdir()):
        if img.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        caption_path = img.with_suffix(".txt")
        if not caption_path.exists():
            caption_path.write_text(DEFAULT_CAPTION)


def write_yaml(
    *,
    name: str,
    images_dir: Path,
    output_dir: Path,
    steps: int = 1000,
    model_id: str | None = None,
) -> Path:
    settings = get_settings()
    model_id = model_id or settings.flux2_model_id
    output_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = output_dir / f"{name}.yaml"
    cfg_path.write_text(textwrap.dedent(f"""\
        job: extension
        config:
          name: "{name}"
          process:
            - type: 'sd_trainer'
              training_folder: "{output_dir}"
              device: cuda:0
              trigger_word: "{TRIGGER_WORD}"
              network:
                type: "lora"
                linear: 16
                linear_alpha: 1
              save:
                dtype: float16
                save_every: 250
                max_step_saves_to_keep: 4
              datasets:
                - folder_path: "{images_dir}"
                  caption_ext: "txt"
                  caption_dropout_rate: 0.05
                  shuffle_tokens: false
                  cache_latents_to_disk: true
                  resolution: [512, 768, 1024]
              train:
                batch_size: 1
                steps: {steps}
                gradient_accumulation_steps: 1
                train_unet: true
                train_text_encoder: false
                gradient_checkpointing: true
                noise_scheduler: "flowmatch"
                optimizer: "adamw8bit"
                lr: 4e-4
                ema_config:
                  use_ema: true
                  ema_decay: 0.99
                dtype: bf16
              model:
                name_or_path: "{model_id}"
                is_flux: true
                quantize: true
                low_vram: true
              sample:
                sampler: "flowmatch"
                sample_every: 250
                width: 1024
                height: 1024
                prompts:
                  - "{TRIGGER_WORD} portrait, ultra-realistic, professional photo"
                  - "{TRIGGER_WORD} wearing casual clothes, outdoor setting"
                neg: ""
                seed: 42
                walk_seed: true
                guidance_scale: 4
                sample_steps: 20
        meta:
          name: "{name}"
          version: '1.0'
        """))
    return cfg_path


def run_aitoolkit(config_path: Path) -> None:
    settings = get_settings()
    ai_python = settings.ai_toolkit_dir / ".venv" / "bin" / "python"
    python = str(ai_python) if ai_python.exists() else sys.executable
    env = os.environ.copy()
    env.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    if settings.hf_token:
        env["HF_TOKEN"] = settings.hf_token
    log.info("ai_toolkit_starting", config=str(config_path))
    subprocess.run(
        [python, str(settings.ai_toolkit_dir / "run.py"), str(config_path)],
        cwd=str(settings.ai_toolkit_dir),
        env=env,
        check=True,
    )
    log.info("ai_toolkit_finished", config=str(config_path))


def expected_output(name: str, output_dir: Path) -> Path:
    """ai-toolkit writes to {training_folder}/{name}/{name}.safetensors"""
    return output_dir / name / f"{name}.safetensors"
