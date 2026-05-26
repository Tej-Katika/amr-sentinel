"""BOCPD tests.

The Beta-Bernoulli BOCPD should: keep changepoint probability low under a stable
rate, then spike it after a clear distributional shift.
"""
import random

from surveillance.bocpd import BOCPD

random.seed(13)


def test_low_changepoint_prob_under_stable_rate():
    bocpd = BOCPD()
    max_cp_prob = 0.0
    for _ in range(200):
        obs = 1 if random.random() < 0.20 else 0
        _, cp_prob = bocpd.update(obs)
        max_cp_prob = max(max_cp_prob, cp_prob)
    assert max_cp_prob < 0.5, f"Spurious changepoint detected under stable rate: max={max_cp_prob:.3f}"


def test_detects_shift():
    """Feed 100 obs at p=0.10, then 100 at p=0.70. The probability of a
    changepoint should rise during the second segment."""
    bocpd = BOCPD()
    # Stable phase
    for _ in range(100):
        bocpd.update(1 if random.random() < 0.10 else 0)
    # Shift phase
    detected_high = False
    for _ in range(100):
        _, cp_prob = bocpd.update(1 if random.random() < 0.70 else 0)
        if cp_prob > 0.5:
            detected_high = True
            break
    assert detected_high, "BOCPD did not flag changepoint after a 0.10 -> 0.70 shift"


def test_state_roundtrip():
    """The serialize/restore path must preserve enough state for inference to continue."""
    a = BOCPD()
    for _ in range(50):
        a.update(1 if random.random() < 0.30 else 0)

    b = BOCPD.from_state_dict(a.get_state_dict())
    assert (a.run_length_probs == b.run_length_probs).all()
    assert (a.alphas == b.alphas).all()
    assert (a.betas == b.betas).all()
