"""Breakpoint engine tests against the seed CSV.

Uses E. coli + Ciprofloxacin + MIC where the seed has S<=0.25, R>0.5.
"""
from pathlib import Path

from breakpoints.engine import BreakpointEngine

SEED_CSV = Path(__file__).resolve().parents[3] / "data" / "breakpoints" / "eucast_seed.csv"


def _engine() -> BreakpointEngine:
    eng = BreakpointEngine()
    eng.load(str(SEED_CSV))
    return eng


def test_loads_seed():
    eng = _engine()
    assert len(eng.breakpoints) > 50, "Seed file should have at least 50 breakpoints"


def test_ecoli_cipro_classifications():
    """E. coli + Ciprofloxacin: S<=0.25, R>0.5."""
    eng = _engine()
    s = eng.classify(562, "J01MA02", "MIC", value=0.125)
    i = eng.classify(562, "J01MA02", "MIC", value=0.5)   # > S threshold, <= R threshold
    r = eng.classify(562, "J01MA02", "MIC", value=4.0)   # > R threshold
    assert s and s.sir == "S"
    assert i and i.sir == "I"
    assert r and r.sir == "R"


def test_disk_method_orientation():
    """For disk diffusion (mm), HIGHER values are more susceptible — the engine
    must invert the comparison vs MIC."""
    eng = _engine()
    # Find a DISK breakpoint in the seed
    disk_bp = next(
        (bp for bp in eng.breakpoints.values() if bp.method == "DISK"),
        None,
    )
    if disk_bp is None:
        return  # seed has no disk-method rules — that's fine
    s = eng.classify(disk_bp.organism_taxid, disk_bp.antibiotic_atc, "DISK",
                     value=disk_bp.s_threshold + 5.0)
    r = eng.classify(disk_bp.organism_taxid, disk_bp.antibiotic_atc, "DISK",
                     value=disk_bp.r_threshold - 5.0)
    assert s and s.sir == "S"
    assert r and r.sir == "R"


def test_returns_none_for_unknown_combination():
    eng = _engine()
    assert eng.classify(99999, "J99XX99", "MIC", value=1.0) is None


def test_records_breakpoint_provenance():
    eng = _engine()
    result = eng.classify(562, "J01MA02", "MIC", value=4.0)
    assert result is not None
    assert result.standard == "EUCAST"
    assert result.version  # any non-empty version string
