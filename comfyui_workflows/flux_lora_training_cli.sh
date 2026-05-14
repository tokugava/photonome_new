#!/bin/bash
# Flux LoRA training via ai-toolkit CLI (recommended for DGX Spark).
# Equivalent to what Replicate's fast-flux-trainer does, running locally.
#
# Setup:
#   git clone https://github.com/ostris/ai-toolkit
#   cd ai-toolkit && pip install -r requirements.txt
#
# Usage:
#   ./flux_lora_training_cli.sh <images_dir> <output_name> [steps]
#
# Example:
#   ./flux_lora_training_cli.sh /data/user123_photos user123_lora 1000

set -e

IMAGES_DIR="${1:?Usage: $0 <images_dir> <output_name> [steps]}"
OUTPUT_NAME="${2:?Usage: $0 <images_dir> <output_name> [steps]}"
STEPS="${3:-1000}"

AI_TOOLKIT_DIR="${AI_TOOLKIT_DIR:-/opt/ai-toolkit}"
COMFYUI_LORAS_DIR="${COMFYUI_LORAS_DIR:-/opt/ComfyUI/models/loras}"
FLUX_MODEL_DIR="${FLUX_MODEL_DIR:-/opt/ComfyUI/models/unet}"

CONFIG_FILE="/tmp/flux_lora_${OUTPUT_NAME}.yaml"

cat > "$CONFIG_FILE" <<YAML
job: extension
config:
  name: "${OUTPUT_NAME}"
  process:
    - type: 'sd_trainer'
      training_folder: "${COMFYUI_LORAS_DIR}"
      device: cuda:0
      trigger_word: "TOK"
      network:
        type: "lora"
        linear: 16
        linear_alpha: 1
      save:
        dtype: float16
        save_every: 250
        max_step_saves_to_keep: 4
      datasets:
        - folder_path: "${IMAGES_DIR}"
          caption_ext: "txt"
          caption_dropout_rate: 0.05
          shuffle_tokens: false
          cache_latents_to_disk: true
          resolution: [512, 768, 1024]
      train:
        batch_size: 1
        steps: ${STEPS}
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
        name_or_path: "${FLUX_MODEL_DIR}/flux1-dev.safetensors"
        is_flux: true
        quantize: true
      sample:
        sampler: "flowmatch"
        sample_every: 250
        width: 1024
        height: 1024
        prompts:
          - "TOK portrait, ultra-realistic, professional photo"
          - "TOK wearing casual clothes, outdoor setting"
        neg: ""
        seed: 42
        walk_seed: true
        guidance_scale: 4
        sample_steps: 20
meta:
  name: "${OUTPUT_NAME}"
  version: '1.0'
YAML

echo "Starting Flux LoRA training: ${OUTPUT_NAME} for ${STEPS} steps"
echo "Images: ${IMAGES_DIR}"
echo "Output: ${COMFYUI_LORAS_DIR}/${OUTPUT_NAME}.safetensors"

cd "$AI_TOOLKIT_DIR"
python run.py "$CONFIG_FILE"

echo "Training complete. LoRA saved to: ${COMFYUI_LORAS_DIR}/${OUTPUT_NAME}.safetensors"
rm -f "$CONFIG_FILE"
