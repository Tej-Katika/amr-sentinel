"""Pydantic models matching the Avro ValidatedIsolateEvent schema.

These are the types that flow through the pipeline:
    parser -> RawIsolate -> validator -> ValidatedIsolateEvent -> Kafka
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MeasurementType(str, Enum):
    MIC = "MIC"
    DISK = "DISK"


class InfectionOrigin(str, Enum):
    COMMUNITY = "COMMUNITY"
    HOSPITAL = "HOSPITAL"
    UNKNOWN = "UNKNOWN"


class SourceFormat(str, Enum):
    WHONET = "WHONET"
    CSV = "CSV"
    FHIR = "FHIR"
    MANUAL = "MANUAL"


class RawIsolate(BaseModel):
    """A single isolate-antibiotic test result before validation.

    Parsers emit RawIsolate; the validator converts to ValidatedIsolateEvent.
    Most fields are optional because raw data is messy.
    """
    facility_id: str
    specimen_id: str
    specimen_type: Optional[str] = None
    organism_input: str = Field(..., description="Organism code or free-text name")
    antibiotic_input: str = Field(..., description="Antibiotic code or free-text name")
    measurement_type: MeasurementType
    measurement_value: float
    measurement_comparator: Optional[str] = None
    patient_age_group: Optional[str] = None
    patient_sex: Optional[str] = None
    ward_id: Optional[str] = None
    infection_origin: Optional[InfectionOrigin] = None
    collection_date: str = Field(..., description="ISO 8601 date")
    source_format: SourceFormat


class ValidatedIsolateEvent(BaseModel):
    """The post-validation schema. Mirrors validated_isolate.avsc."""
    event_id: str
    facility_id: str
    specimen_id: str
    specimen_type: Optional[str] = None
    organism_taxid: int
    organism_name: str
    gram_stain: Optional[str] = None
    antibiotic_atc: str
    antibiotic_name: str
    drug_class: Optional[str] = None
    measurement_type: MeasurementType
    measurement_value: float
    measurement_comparator: Optional[str] = None
    patient_age_group: Optional[str] = None
    patient_sex: Optional[str] = None
    ward_id: Optional[str] = None
    infection_origin: Optional[InfectionOrigin] = None
    collection_date: str
    ingested_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    source_format: SourceFormat


class ValidationFailure(BaseModel):
    """Emitted when validation fails. Sent to dlq.validation_failures."""
    facility_id: Optional[str] = None
    raw_payload: dict
    reason: str
    failed_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
