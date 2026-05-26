"""WHONET parser tests."""
from services.ingestion.models import MeasurementType
from services.ingestion.parsers.whonet import parse_whonet


SAMPLE_TAB_FILE = """LAB_ID\tSPEC_NUM\tSPEC_TYPE\tORG\tDATE_SPEC\tAGE\tSEX\tWARD\tAMP_NM\tCIP_NM\tFOX_ND
HOSP_001\tSPEC-001\tbl\teco\t2026-04-15\t42\tF\tICU\t16\t4\t.
HOSP_001\tSPEC-002\tur\tkpn\t2026-04-15\t65\tM\tGEN\t8\t0.125\t22
HOSP_001\tSPEC-003\tbl\tsau\t2026-04-15\t30\tM\tICU\tR\tS\t18
"""


def test_pivots_wide_to_long():
    """Each (specimen, antibiotic) cell with a numeric value becomes one event."""
    raws = list(parse_whonet(SAMPLE_TAB_FILE))
    # SPEC-001: AMP=16, CIP=4 -> 2 events (FOX is "."  = skip)
    # SPEC-002: AMP=8, CIP=0.125, FOX=22 -> 3 events
    # SPEC-003: AMP=R, CIP=S -> 0 events from those, FOX=18 -> 1 event
    assert len(raws) == 6


def test_extracts_facility_and_specimen():
    raws = list(parse_whonet(SAMPLE_TAB_FILE))
    assert all(r.facility_id == "HOSP_001" for r in raws)
    assert {r.specimen_id for r in raws} == {"SPEC-001", "SPEC-002", "SPEC-003"}


def test_method_suffix_drives_measurement_type():
    """*_NM = MIC, *_ND = DISK."""
    raws = list(parse_whonet(SAMPLE_TAB_FILE))
    cip_events = [r for r in raws if r.antibiotic_input == "CIP"]
    fox_events = [r for r in raws if r.antibiotic_input == "FOX"]
    assert all(r.measurement_type == MeasurementType.MIC for r in cip_events)
    assert all(r.measurement_type == MeasurementType.DISK for r in fox_events)


def test_skips_non_numeric_cells():
    """Cells containing 'R', 'S', 'I' or '.' should be skipped (no numeric value)."""
    raws = list(parse_whonet(SAMPLE_TAB_FILE))
    # SPEC-003 had AMP=R, CIP=S — neither should appear
    spec3 = [r for r in raws if r.specimen_id == "SPEC-003"]
    assert all(r.antibiotic_input not in {"AMP", "CIP"} for r in spec3)


def test_default_facility_id_used_when_absent():
    """Files without a LAB_ID column should fall back to the default."""
    no_lab_id = """SPEC_NUM\tORG\tDATE_SPEC\tCIP_NM
SPEC-001\teco\t2026-04-15\t4
"""
    raws = list(parse_whonet(no_lab_id, default_facility_id="FALLBACK_FAC"))
    assert len(raws) == 1
    assert raws[0].facility_id == "FALLBACK_FAC"
