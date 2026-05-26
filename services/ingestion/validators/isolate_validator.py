"""Convert a RawIsolate to a ValidatedIsolateEvent or a ValidationFailure."""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Union

from ..models import (
    InfectionOrigin,
    MeasurementType,
    RawIsolate,
    SourceFormat,
    ValidatedIsolateEvent,
    ValidationFailure,
)
from .taxonomy import get_resolver

# MIC: typically 0.001 - 1024 ug/mL
# DISK: 6mm (disk diameter) - 50mm
MIC_MIN, MIC_MAX = 0.001, 4096.0
DISK_MIN, DISK_MAX = 6.0, 60.0


def validate(raw: RawIsolate) -> Union[ValidatedIsolateEvent, ValidationFailure]:
    resolver = get_resolver()

    # Organism
    organism = resolver.resolve_organism(raw.organism_input)
    if organism is None:
        return _fail(raw, f"Unresolvable organism: {raw.organism_input!r}")

    # Antibiotic
    abx = resolver.resolve_antibiotic(raw.antibiotic_input)
    if abx is None:
        return _fail(raw, f"Unresolvable antibiotic: {raw.antibiotic_input!r}")

    # Measurement bounds
    if raw.measurement_type == MeasurementType.MIC:
        if not (MIC_MIN <= raw.measurement_value <= MIC_MAX):
            return _fail(raw, f"MIC value {raw.measurement_value} outside plausible range [{MIC_MIN}, {MIC_MAX}]")
    else:  # DISK
        if not (DISK_MIN <= raw.measurement_value <= DISK_MAX):
            return _fail(raw, f"Disk zone {raw.measurement_value} outside plausible range [{DISK_MIN}, {DISK_MAX}]")

    # Date
    try:
        collection_dt = _parse_date(raw.collection_date)
    except ValueError as exc:
        return _fail(raw, f"Invalid collection_date: {exc}")

    if collection_dt > datetime.utcnow():
        return _fail(raw, f"Collection date is in the future: {raw.collection_date}")

    return ValidatedIsolateEvent(
        event_id=str(uuid.uuid4()),
        facility_id=raw.facility_id,
        specimen_id=raw.specimen_id,
        specimen_type=_normalize_specimen_type(raw.specimen_type),
        organism_taxid=organism.taxid,
        organism_name=organism.name,
        gram_stain=organism.gram_stain,
        antibiotic_atc=abx.atc,
        antibiotic_name=abx.name,
        drug_class=abx.drug_class,
        measurement_type=raw.measurement_type,
        measurement_value=raw.measurement_value,
        measurement_comparator=raw.measurement_comparator,
        patient_age_group=_normalize_age_group(raw.patient_age_group),
        patient_sex=_normalize_sex(raw.patient_sex),
        ward_id=raw.ward_id,
        infection_origin=raw.infection_origin or InfectionOrigin.UNKNOWN,
        collection_date=collection_dt.date().isoformat(),
        source_format=raw.source_format,
    )


def _fail(raw: RawIsolate, reason: str) -> ValidationFailure:
    return ValidationFailure(
        facility_id=raw.facility_id,
        raw_payload=raw.model_dump(mode="json"),
        reason=reason,
    )


_DATE_PATTERNS = [
    "%Y-%m-%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%Y",
]


def _parse_date(value: str) -> datetime:
    value = value.strip()
    for pattern in _DATE_PATTERNS:
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            continue
    raise ValueError(f"Could not parse date: {value!r}")


_SPECIMEN_MAP = {
    "bl": "BLOOD", "blood": "BLOOD", "bld": "BLOOD",
    "ur": "URINE", "urine": "URINE",
    "re": "RESPIRATORY", "respiratory": "RESPIRATORY", "sputum": "RESPIRATORY",
    "wo": "WOUND", "wound": "WOUND", "tissue": "WOUND",
    "csf": "CSF", "cerebrospinal": "CSF",
    "st": "STOOL", "stool": "STOOL",
}


def _normalize_specimen_type(value: str | None) -> str | None:
    if not value:
        return None
    return _SPECIMEN_MAP.get(value.strip().lower(), value.strip().upper())


_SEX_MAP = {"m": "M", "male": "M", "f": "F", "female": "F"}


def _normalize_sex(value: str | None) -> str | None:
    if not value:
        return None
    return _SEX_MAP.get(value.strip().lower(), "U")


_AGE_GROUP_BUCKETS = [
    (0, 4, "0-4"),
    (5, 14, "5-14"),
    (15, 24, "15-24"),
    (25, 34, "25-34"),
    (35, 44, "35-44"),
    (45, 54, "45-54"),
    (55, 64, "55-64"),
    (65, 200, "65+"),
]


def _normalize_age_group(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip()
    # Already in canonical form
    if re.match(r"^(\d+-\d+|\d+\+)$", v):
        return v
    # Numeric age: bucket it
    try:
        age = int(float(v))
    except ValueError:
        return v.upper()  # pass through unknown labels
    for lo, hi, label in _AGE_GROUP_BUCKETS:
        if lo <= age <= hi:
            return label
    return None
