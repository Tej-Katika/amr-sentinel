"""Orchestrates: parse -> validate -> de-identify -> publish."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from .kafka_io.producer import get_producer
from .models import RawIsolate, ValidatedIsolateEvent, ValidationFailure
from .validators.deidentify import enforce_k_anonymity
from .validators.isolate_validator import validate

log = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    accepted: int
    failed: int
    events: list[ValidatedIsolateEvent]
    failures: list[ValidationFailure]

    def as_summary(self) -> dict:
        return {
            "accepted": self.accepted,
            "failed": self.failed,
            "first_failures": [f.reason for f in self.failures[:5]],
        }


def run_pipeline(raws: Iterable[RawIsolate], *, deidentify: bool = True) -> PipelineResult:
    events: list[ValidatedIsolateEvent] = []
    failures: list[ValidationFailure] = []

    for raw in raws:
        result = validate(raw)
        if isinstance(result, ValidatedIsolateEvent):
            events.append(result)
        else:
            failures.append(result)

    if deidentify and events:
        events = enforce_k_anonymity(events)

    producer = get_producer()
    producer.publish_validated(events)
    producer.publish_failures(failures)
    producer.flush()

    log.info("Pipeline result: accepted=%d failed=%d", len(events), len(failures))
    return PipelineResult(
        accepted=len(events),
        failed=len(failures),
        events=events,
        failures=failures,
    )
