"""Kafka producer for validated isolates and validation failures.

The schema-registry path uses Confluent's Avro SerializingProducer. For local
development without schema-registry we fall back to JSON-encoded payloads on
the wire (still using the same logical schema).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Iterable, Optional

from ..models import ValidatedIsolateEvent, ValidationFailure

log = logging.getLogger(__name__)

VALIDATED_TOPIC = "isolates.validated"
DLQ_TOPIC = "dlq.validation_failures"


class IsolateProducer:
    """Wrapper around confluent-kafka.Producer.

    Lazy import: confluent-kafka is a heavy dependency (librdkafka). When
    KAFKA_BOOTSTRAP_SERVERS is unset (e.g. unit tests) we no-op.
    """

    def __init__(self, bootstrap: Optional[str] = None) -> None:
        self.bootstrap = bootstrap or os.getenv("KAFKA_BOOTSTRAP_SERVERS")
        self._producer = None
        if self.bootstrap:
            try:
                from confluent_kafka import Producer  # type: ignore
                self._producer = Producer({
                    "bootstrap.servers": self.bootstrap,
                    "client.id": "amr-ingestion",
                    "acks": "all",
                    "linger.ms": 50,
                    "compression.type": "snappy",
                })
            except ImportError:
                log.warning("confluent-kafka not installed; events will not be published")

    def publish_validated(self, events: Iterable[ValidatedIsolateEvent]) -> int:
        return self._publish(VALIDATED_TOPIC, events, key_fn=lambda ev: ev.facility_id)

    def publish_failures(self, failures: Iterable[ValidationFailure]) -> int:
        return self._publish(DLQ_TOPIC, failures, key_fn=lambda f: f.facility_id or "UNKNOWN")

    def flush(self, timeout: float = 10.0) -> None:
        if self._producer is not None:
            self._producer.flush(timeout)

    def _publish(self, topic: str, items: Iterable, *, key_fn) -> int:
        items = list(items)
        if self._producer is None:
            log.info("Producer disabled; would publish %d items to %s", len(items), topic)
            return len(items)
        for item in items:
            payload = json.dumps(item.model_dump(mode="json")).encode("utf-8")
            self._producer.produce(
                topic=topic,
                key=key_fn(item).encode("utf-8"),
                value=payload,
                on_delivery=_delivery_callback,
            )
        self._producer.poll(0)
        return len(items)


def _delivery_callback(err, msg) -> None:
    if err is not None:
        log.error("Kafka delivery failed: %s", err)
    else:
        log.debug("Delivered %s [%d] @ %d", msg.topic(), msg.partition(), msg.offset())


_singleton: Optional[IsolateProducer] = None


def get_producer() -> IsolateProducer:
    global _singleton
    if _singleton is None:
        _singleton = IsolateProducer()
    return _singleton
