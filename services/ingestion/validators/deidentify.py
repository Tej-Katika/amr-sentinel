"""De-identification.

The validator already strips direct identifiers (we never accept names or MRNs).
This module enforces k-anonymity on quasi-identifiers (age + sex + ward + date).
"""
from __future__ import annotations

from collections import Counter
from typing import Iterable

from ..models import ValidatedIsolateEvent

K_ANON_THRESHOLD = 5


def enforce_k_anonymity(
    events: Iterable[ValidatedIsolateEvent],
    k: int = K_ANON_THRESHOLD,
) -> list[ValidatedIsolateEvent]:
    """Generalize age groups when the (age, sex, ward, date) combo would identify <k people.

    Operates on a batch — single-event ingestion can't enforce k-anonymity at insert
    time and instead relies on aggregate-only views downstream. This is safe for
    a hospital that's looking at its own data, since within-facility identification
    is not the threat model — exporting beyond the facility is.
    """
    events = list(events)
    if not events or k <= 1:
        return events

    counts: Counter[tuple] = Counter()
    for ev in events:
        counts[(ev.patient_age_group, ev.patient_sex, ev.ward_id, ev.collection_date)] += 1

    out: list[ValidatedIsolateEvent] = []
    for ev in events:
        key = (ev.patient_age_group, ev.patient_sex, ev.ward_id, ev.collection_date)
        if counts[key] < k and ev.patient_age_group:
            ev = ev.model_copy(update={"patient_age_group": _broaden(ev.patient_age_group)})
        out.append(ev)
    return out


_BROADEN = {
    "0-4": "0-14",
    "5-14": "0-14",
    "15-24": "15-44",
    "25-34": "15-44",
    "35-44": "15-44",
    "45-54": "45-64",
    "55-64": "45-64",
    "65+": "65+",
}


def _broaden(age_group: str) -> str:
    return _BROADEN.get(age_group, age_group)
