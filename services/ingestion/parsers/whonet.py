"""WHONET parser.

WHONET exports tab- or comma-delimited files where each row is one isolate,
and antibiotic results are columns named like 'AMP_ND10' (Ampicillin disk
diffusion 10ug). We pivot wide -> long: one RawIsolate per cell.
"""
from __future__ import annotations

import csv
import io
import re
from typing import Iterator

from ..models import MeasurementType, RawIsolate, SourceFormat

# WHONET antibiotic column convention:
#   <CODE>_<METHOD><DOSE>
# Examples: "AMP_ND10" = Ampicillin, ND=disk diffusion (Neo-Sensitabs disk?)
#           "CIP_NM"   = Ciprofloxacin, NM=MIC
#           "VAN_ED"   = Vancomycin, ED=Etest disk (MIC equivalent)
#
# Common method suffixes:
#   ND, DD, KB         = disk diffusion (mm)
#   NM, ME, ET         = MIC (ug/mL)
ANTIBIOTIC_COL_RE = re.compile(r"^([A-Z]{2,4})(?:_([A-Z]+\d*))?$")

DISK_METHODS = {"ND", "DD", "KB", "BD"}
MIC_METHODS = {"NM", "ME", "ET", "MI", "EM"}

# WHONET core columns we care about
KEY_COLS = {
    "facility_id":    ["LAB_ID", "LABORATORY", "LAB", "FACILITY_ID"],
    "specimen_id":    ["SPEC_NUM", "SPECIMEN", "SPECIMEN_ID", "ISOLATE_ID"],
    "specimen_type":  ["SPEC_TYPE", "SPECIMEN_TYPE", "SAMPLE_TYPE"],
    "organism":       ["ORG", "ORGANISM"],
    "collection_date":["DATE_SPEC", "SPEC_DATE", "COLLECTION_DATE", "DATE"],
    "patient_age":    ["AGE", "PATIENT_AGE"],
    "patient_sex":    ["SEX", "GENDER"],
    "ward":           ["WARD", "DEPARTMENT", "LOCATION"],
}


def parse_whonet(content: str, default_facility_id: str | None = None) -> Iterator[RawIsolate]:
    """Parse a WHONET tab- or comma-delimited export into RawIsolate events.

    Args:
        content: Raw file contents as text.
        default_facility_id: Used when the file has no LAB_ID column.
    """
    delimiter = _detect_delimiter(content)
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    if reader.fieldnames is None:
        return

    col_lookup = {c.upper().strip(): c for c in reader.fieldnames}
    key_cols = {field: _first_match(col_lookup, names) for field, names in KEY_COLS.items()}

    abx_cols: list[tuple[str, str, str]] = []  # (column, abx_code, method)
    for col in reader.fieldnames:
        match = ANTIBIOTIC_COL_RE.match(col.upper())
        if not match:
            continue
        code, method = match.group(1), match.group(2) or ""
        if not method:
            continue
        if method in DISK_METHODS or method in MIC_METHODS:
            abx_cols.append((col, code, method))

    for row in reader:
        facility = (
            (key_cols["facility_id"] and row.get(key_cols["facility_id"])) or default_facility_id
        )
        specimen_id = key_cols["specimen_id"] and row.get(key_cols["specimen_id"])
        organism_code = key_cols["organism"] and row.get(key_cols["organism"])
        collection_date = key_cols["collection_date"] and row.get(key_cols["collection_date"])

        if not (facility and specimen_id and organism_code and collection_date):
            continue

        for col, abx_code, method in abx_cols:
            raw_value = row.get(col)
            parsed = _parse_measurement(raw_value)
            if parsed is None:
                continue
            value, comparator = parsed
            measurement_type = (
                MeasurementType.MIC if method in MIC_METHODS else MeasurementType.DISK
            )

            yield RawIsolate(
                facility_id=facility,
                specimen_id=specimen_id,
                specimen_type=key_cols["specimen_type"] and row.get(key_cols["specimen_type"]),
                organism_input=organism_code,
                antibiotic_input=abx_code,
                measurement_type=measurement_type,
                measurement_value=value,
                measurement_comparator=comparator,
                patient_age_group=key_cols["patient_age"] and row.get(key_cols["patient_age"]),
                patient_sex=key_cols["patient_sex"] and row.get(key_cols["patient_sex"]),
                ward_id=key_cols["ward"] and row.get(key_cols["ward"]),
                collection_date=collection_date,
                source_format=SourceFormat.WHONET,
            )


def _detect_delimiter(content: str) -> str:
    first_line = content.split("\n", 1)[0]
    return "\t" if first_line.count("\t") >= first_line.count(",") else ","


def _first_match(lookup: dict[str, str], candidates: list[str]) -> str | None:
    for c in candidates:
        if c in lookup:
            return lookup[c]
    return None


_VALUE_RE = re.compile(r"^\s*(<=|>=|<|>|=)?\s*(\d+(?:\.\d+)?)\s*$")


def _parse_measurement(raw: str | None) -> tuple[float, str | None] | None:
    """Parse a WHONET cell to (value, comparator).

    Returns None if the cell is blank, unreadable, or contains a special code
    like 'R' or 'S' (no measurement).
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    # Skip cells that are just SIR letters with no numeric measurement
    if s.upper() in {"R", "S", "I", "ND", "NA", "."}:
        return None
    match = _VALUE_RE.match(s)
    if not match:
        return None
    comparator = match.group(1)
    value = float(match.group(2))
    return value, comparator
