"""Taxonomy resolver tests — exact + fuzzy matching for organisms and antibiotics."""
from services.ingestion.validators.taxonomy import get_resolver


def test_organism_by_whonet_code():
    r = get_resolver()
    assert r.resolve_organism("eco").taxid == 562
    assert r.resolve_organism("ECO").taxid == 562  # case-insensitive
    assert r.resolve_organism("kpn").taxid == 573


def test_organism_by_full_name():
    r = get_resolver()
    assert r.resolve_organism("Escherichia coli").taxid == 562
    assert r.resolve_organism("E. coli").taxid == 562


def test_organism_fuzzy_fallback():
    r = get_resolver()
    # Slight typo should still match via fuzzy
    rec = r.resolve_organism("Escherchia coli")
    assert rec is not None
    assert rec.taxid == 562


def test_organism_unresolvable_returns_none():
    r = get_resolver()
    assert r.resolve_organism("Unknown bacterium 1234") is None


def test_antibiotic_by_whonet_code():
    r = get_resolver()
    assert r.resolve_antibiotic("CIP").atc == "J01MA02"
    assert r.resolve_antibiotic("AMP").atc == "J01CA01"


def test_antibiotic_by_atc_code():
    r = get_resolver()
    assert r.resolve_antibiotic("J01MA02").name == "Ciprofloxacin"


def test_antibiotic_with_method_suffix():
    """WHONET columns are like 'AMP_ND10' — the resolver should strip the suffix."""
    r = get_resolver()
    assert r.resolve_antibiotic("AMP_ND10").atc == "J01CA01"
    assert r.resolve_antibiotic("CIP_NM").atc == "J01MA02"


def test_antibiotic_by_name():
    r = get_resolver()
    assert r.resolve_antibiotic("ciprofloxacin").atc == "J01MA02"
    assert r.resolve_antibiotic("Ciprofloxacin").atc == "J01MA02"


def test_antibiotic_unresolvable():
    r = get_resolver()
    assert r.resolve_antibiotic("ZZZ_FAKE") is None
