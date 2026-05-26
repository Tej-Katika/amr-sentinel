"""Binary CUSUM for AMR surveillance.

Reference: CDC 2002, "Application of CUSUM to hospital infection surveillance."
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CUSUMState:
    facility_id: str
    organism_taxid: int
    antibiotic_atc: str
    cusum_sum: float = 0.0
    baseline_rate: float = 0.0
    reference_value: float = 0.0
    threshold: float = 4.0
    observations: int = 0


def initialize_cusum(baseline_rate: float, relative_increase: float = 1.5) -> dict:
    """Compute reference value (k) and threshold (h) from a baseline rate.

    Returns:
        Dict with 'k', 'h', 'p0', 'p1'.
    """
    p0 = max(min(baseline_rate, 0.99), 0.001)
    p1 = min(p0 * relative_increase, 0.99)
    k = (p0 + p1) / 2  # binary CUSUM reference: midpoint of p0, p1
    h = 4.0  # ARL ~ 50 under null; tunable per facility
    return {"k": k, "h": h, "p0": p0, "p1": p1}


def update_cusum(state: CUSUMState, observation: int) -> tuple[CUSUMState, bool]:
    """Process one observation through the CUSUM and report whether an alert fired."""
    new_sum = max(0.0, state.cusum_sum + (observation - state.reference_value))
    state.cusum_sum = new_sum
    state.observations += 1

    alert = new_sum >= state.threshold
    if alert:
        state.cusum_sum = 0.0  # reset after alert
    return state, alert
