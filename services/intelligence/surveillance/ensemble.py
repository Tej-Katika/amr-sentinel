"""Fuse CUSUM and BOCPD into a unified severity level."""
from __future__ import annotations

from enum import Enum


class AlertSeverity(str, Enum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    INVESTIGATE = "INVESTIGATE"
    NONE = "NONE"


def fuse_alerts(cusum_fired: bool, bocpd_fired: bool) -> AlertSeverity:
    if cusum_fired and bocpd_fired:
        return AlertSeverity.HIGH
    if cusum_fired:
        return AlertSeverity.MODERATE
    if bocpd_fired:
        return AlertSeverity.INVESTIGATE
    return AlertSeverity.NONE
