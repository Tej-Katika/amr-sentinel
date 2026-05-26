"""Spatiotemporal clustering for outbreak detection.

Sliding-window approach: if N or more resistant isolates of the same organism
appear in the same ward within D days, emit a cluster alert.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class ClusterAlert:
    facility_id: str
    ward_id: str
    organism_taxid: int
    organism_name: str
    isolate_count: int
    window_days: int
    earliest_collection_date: str
    latest_collection_date: str


@dataclass
class ClusterDetectorState:
    """In-memory rolling window per (facility, ward, organism). Persist if needed."""
    cluster_threshold: int = 3
    window_days: int = 7
    # key -> deque of (collection_date, specimen_id)
    windows: dict[tuple[str, str, int], deque] = field(default_factory=lambda: defaultdict(deque))


def update_cluster(
    state: ClusterDetectorState,
    *,
    facility_id: str,
    ward_id: Optional[str],
    organism_taxid: int,
    organism_name: str,
    sir_classification: Optional[str],
    collection_date: str,
    specimen_id: str,
) -> Optional[ClusterAlert]:
    """Update the rolling window with one classified event. Returns a ClusterAlert
    when the window crosses the threshold."""
    if not ward_id or sir_classification != "R":
        return None

    try:
        date = datetime.fromisoformat(collection_date.split("T")[0])
    except ValueError:
        return None

    key = (facility_id, ward_id, organism_taxid)
    window = state.windows[key]

    # Drop entries outside the window
    cutoff = date - timedelta(days=state.window_days)
    while window and window[0][0] < cutoff:
        window.popleft()

    # Avoid double-counting the same specimen
    if any(spec == specimen_id for _, spec in window):
        return None

    window.append((date, specimen_id))

    if len(window) >= state.cluster_threshold:
        return ClusterAlert(
            facility_id=facility_id,
            ward_id=ward_id,
            organism_taxid=organism_taxid,
            organism_name=organism_name,
            isolate_count=len(window),
            window_days=state.window_days,
            earliest_collection_date=window[0][0].date().isoformat(),
            latest_collection_date=window[-1][0].date().isoformat(),
        )
    return None
