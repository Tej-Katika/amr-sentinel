"""Spatiotemporal cluster detector tests."""
from surveillance.clustering import ClusterDetectorState, update_cluster


def _emit(state, day, specimen):
    return update_cluster(
        state,
        facility_id="F1",
        ward_id="ICU1",
        organism_taxid=1280,
        organism_name="Staphylococcus aureus",
        sir_classification="R",
        collection_date=f"2026-04-{day:02d}",
        specimen_id=specimen,
    )


def test_fires_on_threshold():
    state = ClusterDetectorState(cluster_threshold=3, window_days=7)
    assert _emit(state, 10, "S1") is None
    assert _emit(state, 11, "S2") is None
    alert = _emit(state, 12, "S3")
    assert alert is not None
    assert alert.isolate_count == 3
    assert alert.ward_id == "ICU1"


def test_susceptible_isolates_ignored():
    state = ClusterDetectorState(cluster_threshold=2, window_days=7)
    susceptible = update_cluster(
        state,
        facility_id="F1", ward_id="ICU1",
        organism_taxid=1280, organism_name="S. aureus",
        sir_classification="S",
        collection_date="2026-04-10",
        specimen_id="S1",
    )
    assert susceptible is None


def test_window_drops_old_entries():
    """If first event is on day 1 and second is on day 30, the window has expired."""
    state = ClusterDetectorState(cluster_threshold=2, window_days=7)
    _emit(state, 1, "S1")
    alert = _emit(state, 30, "S2")
    assert alert is None  # only one event in the rolling window


def test_no_double_count_same_specimen():
    state = ClusterDetectorState(cluster_threshold=2, window_days=7)
    _emit(state, 10, "SAME")
    alert = _emit(state, 11, "SAME")
    assert alert is None
