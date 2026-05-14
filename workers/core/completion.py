from core.config import get_settings
from core.pubsub import publish


def publish_completion(
    *,
    user_id: str,
    job_id: str,
    kind: str,
    status: str,
    output_path: str | None = None,
    error: str | None = None,
) -> str:
    payload: dict = {"userId": user_id, "jobId": job_id, "kind": kind, "status": status}
    if output_path is not None:
        payload["outputPath"] = output_path
    if error is not None:
        payload["error"] = error
    return publish(get_settings().completions_topic, payload)
