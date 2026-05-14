from pathlib import Path

import firebase_admin
from firebase_admin import credentials, storage

from core.config import get_settings

_initialized = False


def init_app() -> None:
    global _initialized
    if _initialized:
        return
    settings = get_settings()
    cred = credentials.Certificate(str(settings.firebase_credentials))
    firebase_admin.initialize_app(cred, {"storageBucket": settings.firebase_storage_bucket})
    _initialized = True


def _normalize(storage_path: str) -> str:
    if storage_path.startswith("gs://"):
        _, _, rest = storage_path.partition("gs://")
        _, _, blob_path = rest.partition("/")
        return blob_path
    return storage_path.lstrip("/")


def download(storage_path: str, dest: Path) -> Path:
    init_app()
    dest.parent.mkdir(parents=True, exist_ok=True)
    bucket = storage.bucket()
    blob = bucket.blob(_normalize(storage_path))
    blob.download_to_filename(str(dest))
    return dest


def upload(local: Path, storage_path: str, content_type: str | None = None) -> str:
    init_app()
    bucket = storage.bucket()
    blob = bucket.blob(_normalize(storage_path))
    blob.upload_from_filename(str(local), content_type=content_type)
    return f"gs://{bucket.name}/{blob.name}"


def signed_url(storage_path: str, ttl_s: int = 3600) -> str:
    from datetime import timedelta

    init_app()
    bucket = storage.bucket()
    blob = bucket.blob(_normalize(storage_path))
    return blob.generate_signed_url(expiration=timedelta(seconds=ttl_s), method="GET")
