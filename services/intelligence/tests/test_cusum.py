"""CUSUM tests.

The two key invariants:
    1. Under the null (resistance rate = baseline), the CUSUM should rarely fire.
    2. Under a sustained shift to a higher rate, it must fire within a few hundred
       observations.
"""
import random

from surveillance.cusum import CUSUMState, initialize_cusum, update_cusum

random.seed(7)


def _state(baseline: float = 0.20) -> CUSUMState:
    params = initialize_cusum(baseline)
    return CUSUMState(
        facility_id="F", organism_taxid=562, antibiotic_atc="J01MA02",
        baseline_rate=params["p0"], reference_value=params["k"], threshold=params["h"],
    )


def test_initialize_returns_sensible_params():
    p = initialize_cusum(0.20, relative_increase=1.5)
    assert 0.20 <= p["k"] <= 0.30
    assert p["h"] > 0
    assert p["p1"] > p["p0"]


def test_no_alert_under_baseline():
    """1000 observations at the baseline rate should not produce many alerts."""
    state = _state(baseline=0.20)
    alerts = 0
    for _ in range(1000):
        obs = 1 if random.random() < 0.20 else 0
        state, fired = update_cusum(state, obs)
        if fired:
            alerts += 1
    # ARL ~ 50 means we expect <= 1000/50 = 20 false alarms; allow some slack
    assert alerts < 30, f"Too many false alerts under null: {alerts}"


def test_alert_fires_under_shift():
    """When the actual rate jumps to 50% (vs 20% baseline), we must alert quickly."""
    state = _state(baseline=0.20)
    fired_at = None
    for i in range(500):
        # First 100 observations at baseline, then shift to 0.50
        rate = 0.20 if i < 100 else 0.50
        obs = 1 if random.random() < rate else 0
        state, fired = update_cusum(state, obs)
        if fired:
            fired_at = i - 100  # observations after the shift
            break
    assert fired_at is not None, "CUSUM never fired under sustained shift"
    assert fired_at < 200, f"CUSUM took {fired_at} obs to detect shift — too slow"


def test_resets_after_alert():
    """The sum should reset to 0 after an alert fires (or at least drop substantially)."""
    state = _state(baseline=0.20)
    # Force an alert by feeding all 1s
    for _ in range(20):
        state, fired = update_cusum(state, 1)
        if fired:
            assert state.cusum_sum == 0.0
            return
    raise AssertionError("Forcing all-1s did not produce an alert")
