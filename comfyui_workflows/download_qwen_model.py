#!/usr/bin/env python3
"""
Download and merge Qwen/Qwen-Image-Edit-2511 model files for ComfyUI.

Downloads sharded safetensors from HuggingFace and merges them into
single files expected by the ComfyUI workflows:
  - models/diffusion_models/qwen_image_edit_transformer.safetensors (~50 GB)
  - models/text_encoders/qwen_image_edit_clip.safetensors (~16.5 GB)
  - models/vae/qwen_image_edit_vae.safetensors (~0.25 GB)

Run from the ComfyUI directory or set COMFYUI_DIR env variable.
Requires: pip install huggingface_hub hf_xet safetensors torch
"""

import os
import sys
import json
import shutil
from pathlib import Path

COMFYUI_DIR = Path(os.environ.get("COMFYUI_DIR", "/home/kemal/Projects/ComfyUI"))
MODEL_ID = "Qwen/Qwen-Image-Edit-2511"

DEST = {
    "transformer": COMFYUI_DIR / "models/diffusion_models/qwen_image_edit_transformer.safetensors",
    "text_encoder": COMFYUI_DIR / "models/text_encoders/qwen_image_edit_clip.safetensors",
    "vae": COMFYUI_DIR / "models/vae/qwen_image_edit_vae.safetensors",
}

CACHE_DIR = Path("/tmp/qwen_model_cache")


def download_file(repo_id, filename, cache_dir):
    from huggingface_hub import hf_hub_download
    print(f"  Downloading {filename}...")
    path = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        cache_dir=str(cache_dir),
        local_dir=str(cache_dir / "files"),
    )
    return Path(path)


def get_shard_filenames(repo_id, subfolder, cache_dir):
    """Return list of shard filenames by checking index files with both naming conventions."""
    from huggingface_hub import hf_hub_download
    # Try both HuggingFace naming conventions for index files
    index_candidates = [
        f"{subfolder}/model.safetensors.index.json",
        f"{subfolder}/diffusion_pytorch_model.safetensors.index.json",
    ]
    single_candidates = [
        f"{subfolder}/diffusion_pytorch_model.safetensors",
        f"{subfolder}/model.safetensors",
    ]

    for index_file in index_candidates:
        try:
            path = hf_hub_download(
                repo_id=repo_id,
                filename=index_file,
                cache_dir=str(cache_dir),
                local_dir=str(cache_dir / "files"),
            )
            with open(path) as f:
                index = json.load(f)
            shards = sorted(set(index["weight_map"].values()))
            return [f"{subfolder}/{s}" for s in shards]
        except Exception:
            continue

    # No index found — return whichever single-file candidate exists in the repo
    from huggingface_hub import list_repo_files
    repo_files = set(list_repo_files(repo_id))
    for candidate in single_candidates:
        if candidate in repo_files:
            return [candidate]

    raise FileNotFoundError(f"No safetensors files found in {subfolder}/ for {repo_id}")


def merge_shards(shard_paths, output_path):
    """Merge multiple safetensors shards into a single file."""
    import torch
    from safetensors.torch import load_file, save_file

    print(f"  Merging {len(shard_paths)} shards into {output_path.name}...")
    merged = {}
    for path in shard_paths:
        print(f"    Loading {Path(path).name}...")
        shard = load_file(str(path))
        merged.update(shard)
        del shard

    print(f"    Saving merged file ({len(merged)} tensors)...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_file(merged, str(output_path))
    del merged
    print(f"    Saved to {output_path}")


def download_component(component, subfolder, dest_path):
    if dest_path.exists():
        print(f"[SKIP] {dest_path.name} already exists")
        return

    print(f"\n[{component.upper()}] Downloading from {MODEL_ID}/{subfolder}/")
    shards = get_shard_filenames(MODEL_ID, subfolder, CACHE_DIR)
    print(f"  Found {len(shards)} shard(s)")

    local_paths = []
    for shard in shards:
        local_path = download_file(MODEL_ID, shard, CACHE_DIR)
        local_paths.append(local_path)

    if len(local_paths) == 1:
        print(f"  Copying single file to {dest_path.name}...")
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(local_paths[0]), str(dest_path))
    else:
        merge_shards(local_paths, dest_path)

    print(f"  [DONE] {component}")


def main():
    print(f"ComfyUI directory: {COMFYUI_DIR}")
    print(f"Model: {MODEL_ID}")
    print(f"Cache: {CACHE_DIR}\n")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Download VAE first (smallest, ~0.25 GB)
    download_component("vae", "vae", DEST["vae"])

    # Download text encoder (~16.5 GB)
    download_component("text_encoder", "text_encoder", DEST["text_encoder"])

    # Download transformer (~50 GB)
    download_component("transformer", "transformer", DEST["transformer"])

    print("\n=== All models downloaded successfully ===")
    for name, path in DEST.items():
        size_gb = path.stat().st_size / 1e9 if path.exists() else 0
        print(f"  {name}: {path} ({size_gb:.1f} GB)")


if __name__ == "__main__":
    main()
