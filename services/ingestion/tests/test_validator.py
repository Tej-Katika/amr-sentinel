"""Isolate validator tests."""
from datetime import date, timedelta

from services.ingestion.models import (
    InfectionOrigin,
    MeasurementType,
    RawIsolate,
    SourceFormat,
    ValidatedIsolateEvent,
    ValidationFailure,
)
from services.ingestion.validators.isolate_validator import validate


def _raw(**overrides) -> RawIsolate:
    base = dict(
        facility_id="FACILITY_001",
        specimen_id="SPEC-001",
        organism_input="eco",
        antibiotic_input="CIP",
        measurement_type=MeasurementType.MIC,
        measurement_value=4.0,
        collection_date="2026-04-15",
        source_format=SourceFormat.WHONET,
    )
    base.update(overrides)
    return RawIsolate(**base)


def test_happy_path_returns_validated_event():
    result = validate(_raw())
    assert isinstance(result, ValidatedIsolateEvent)
    assert result.organism_taxid == 562
    assert result.organism_name == "Escherichia coli"
    assert result.antibiotic_atc == "J01MA02"
    assert result.measurement_value == 4.0


def test_unresolvable_organism_fails():
    result = validate(_raw(organism_input="Imaginarium virus"))
    assert isinstance(result, ValidationFailure)
    assert "organism" in result.reason.lower()


def test_unresolvable_antibiotic_fails():
    result = validate(_raw(antibiotic_input="ZZZ_FAKE_DRUG"))
    assert isinstance(result, ValidationFailure)
    assert "antibiotic" in result.reason.lower()


def test_mic_out_of_range_fails():
    result = validate(_raw(measurement_value=999999.0))
    assert isinstance(result, ValidationFailure)
    assert "outside" in result.reason.lower()


def test_disk_value_in_range():
    result = validate(_raw(measurement_type=MeasurementType.DISK, measurement_value=22.0))
    assert isinstance(result, ValidatedIsolateEvent)


def test_disk_below_minimum_fails():
    result = validate(_raw(measurement_type=MeasurementType.DISK, measurement_value=3.0))
    assert isinstance(result, ValidationFailure)


def test_future_date_fails():
    future = (date.today() + timedelta(days=30)).isoformat()
    result = validate(_raw(collection_date=future))
    assert isinstance(result, ValidationFailure)
    assert "future" in result.reason.lower()


def test_unparseable_date_fails():
    result = validate(_raw(collection_date="not-a-date"))
    assert isinstance(result, ValidationFailure)


def test_age_group_normalization_buckets_numeric_age():
    result = validate(_raw(patient_age_group="42"))
    assert isinstance(result, ValidatedIsolateEvent)
    assert result.patient_age_group == "35-44"


def test_age_group_passes_canonical_form():
    result = validate(_raw(patient_age_group="65+"))
    assert isinstance(result, ValidatedIsolateEvent)
    assert result.patient_age_group == "65+"


def test_specimen_type_normalized():
    result = validate(_raw(specimen_type="bl"))
    assert isinstance(result, ValidatedIsolateEvent)
    assert result.specimen_type == "BLOOD"


def test_infection_origin_defaults_to_unknown():
    result = validate(_raw())
    assert isinstance(result, ValidatedIsolateEvent)
    assert result.infection_origin == InfectionOrigin.UNKNOWN
