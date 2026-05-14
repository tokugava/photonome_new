from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="PHOTONOME_", extra="ignore")

    gcp_project: str = "photonome"
    firebase_credentials: Path = Path("/home/kemal/Projects/photonome_new/photonome-firebase-adminsdk-dob69-e40048c4ad.json")
    firebase_storage_bucket: str = "photonome.appspot.com"

    edit_subscription: str = "edit-jobs-sub"
    train_subscription: str = "train-jobs-sub"
    generate_subscription: str = "generate-jobs-sub"
    completions_topic: str = "job-completions"

    flux_kontext_model_id: str = "black-forest-labs/FLUX.1-Kontext-dev"
    flux2_model_id: str = "black-forest-labs/FLUX.2-dev"

    ai_toolkit_dir: Path = Path("/opt/ai-toolkit")
    lora_cache_dir: Path = Path("/var/cache/photonome/loras")
    work_dir: Path = Path("/var/cache/photonome/work")
    vram_lock_dir: Path = Path("/var/run/photonome")

    train_lease_hours: int = 4
    inference_lease_hours: int = 2

    hf_token: str | None = Field(default=None, alias="HF_TOKEN")


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.lora_cache_dir.mkdir(parents=True, exist_ok=True)
    s.work_dir.mkdir(parents=True, exist_ok=True)
    s.vram_lock_dir.mkdir(parents=True, exist_ok=True)
    return s
