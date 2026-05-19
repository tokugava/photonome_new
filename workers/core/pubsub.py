import json
from typing import Callable, NoReturn

import structlog
from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.subscriber.message import Message

from core.config import get_settings

log = structlog.get_logger(__name__)

Handler = Callable[[dict, Message], None]


def run_subscriber(subscription: str, handler: Handler, lease_hours: int = 2) -> NoReturn:
    settings = get_settings()
    subscriber = pubsub_v1.SubscriberClient()
    path = subscriber.subscription_path(settings.gcp_project, subscription)

    flow = pubsub_v1.types.FlowControl(
        max_messages=1,
        max_bytes=10 * 1024 * 1024,
        max_lease_duration=lease_hours * 3600.0,
    )

    def _callback(message: Message) -> None:
        try:
            payload = json.loads(message.data.decode("utf-8"))
        except json.JSONDecodeError as exc:
            log.error("invalid_json", error=str(exc), data=message.data[:200])
            message.ack()
            return

        try:
            handler(payload, message)
        except Exception as exc:
            log.exception("handler_failed", error=str(exc), payload=payload)
            message.nack()
            return

        try:
            message.ack()
        except Exception as exc:
            log.exception("ack_failed", error=str(exc))

    future = subscriber.subscribe(path, callback=_callback, flow_control=flow)
    log.info("subscriber_started", subscription=path, lease_hours=lease_hours)

    try:
        future.result()
    except KeyboardInterrupt:
        future.cancel()
        future.result()
    finally:
        subscriber.close()


def publish(topic: str, payload: dict) -> str:
    settings = get_settings()
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(settings.gcp_project, topic)
    data = json.dumps(payload).encode("utf-8")
    return publisher.publish(topic_path, data).result(timeout=30)
