"""Configurable CSV mapper.

Each facility registers a column mapping (YAML or dict) once. Subsequent
uploads from that facility are auto-parsed.

Mapping schema:
    facility_id: HOSP_042
    column_mappings:
        organism:        "Bacteria"
        antibiotic:      "Drug"
        measurement_type: "Method"        # MIC or DISK column
        measurement_value: "Result"
        specimen_id:     "Specimen ID"
        specimen_type:   "Sample Type"
        collection_date: "Date Collected"
        ward:            "Department"
        age:             "Age"
        sex:             "Sex"
    date_format: "%d/%m/%Y"
    default_measurement_type: "MIC"   # used when no measurement_type column
"""
from __future__ import annotations

import csv
import io
import re
from typing import Iterator

from ..models import MeasurementType, RawIsolate, SourceFormat


def parse_csv(content: str, mapping: dict) -> Iterator[RawIsolate]:
    facility_id = mapping["facility_id"]
    cols = mapping["column_mappings"]
    default_method = mapping.get("default_measurement_type", "MIC").upper()

    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        organism = _get(row, cols.get("organism"))
        antibiotic = _get(row, cols.get("antibiotic"))
        value_raw = _get(row, cols.get("measurement_value"))
        if not (organism and antibiotic and value_raw):
            continue

        parsed = _parse_value(value_raw)
        if parsed is None:
            continue
        value, comparator = parsed

        measurement_type_raw = _get(row, cols.get("measurement_type")) or default_method
        try:
            measurement_type = MeasurementType(measurement_type_raw.strip().upper())
        except ValueError:
            measurement_type = MeasurementType[default_method]

        yield RawIsolate(
            facility_id=facility_id,
            specimen_id=_get(row, cols.get("specimen_id")) or _get(row, cols.get("isolate_id")) or "UNKNOWN",
            specimen_type=_get(row, cols.get("specimen_type")),
            organism_input=organism,
            antibiotic_input=antibiotic,
            measurement_type=measurement_type,
            measurement_value=value,
            measurement_comparator=comparator,
            patient_age_group=_get(row, cols.get("age")),
            patient_sex=_get(row, cols.get("sex")),
            ward_id=_get(row, cols.get("ward")),
            collection_date=_get(row, cols.get("collection_date")) or "",
            source_format=SourceFormat.CSV,
        )


def _get(row: dict, key: str | None) -> str | None:
    if not key:
        return None
    val = row.get(key)
    return val.strip() if isinstance(val, str) and val.strip() else None


_VALUE_RE = re.compile(r"^\s*(<=|>=|<|>|=)?\s*(\d+(?:\.\d+)?)\s*$")


def _parse_value(raw: str) -> tuple[float, str | None] | None:
    s = str(raw).strip()
    if not s:
        return None
    match = _VALUE_RE.match(s)
    if not match:
        return None
    comparator = match.group(1)
    value = float(match.group(2))
    return value, comparator
