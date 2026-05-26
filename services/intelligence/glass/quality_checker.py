"""GLASS quality indicator computation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..db import get_cursor


@dataclass
class QualityIndicators:
    facility_id: str
    year: int
    pct_blood_with_ast: float
    pct_isolates_species_id: float
    n_unique_specimens: int
    n_isolate_results: int
    n_organism_taxa: int
    n_antibiotics_tested: int


def compute(facility_id: str, year: int) -> QualityIndicators:
    period_start = date(year, 1, 1)
    period_end = date(year + 1, 1, 1)

    sql = """
        SELECT
            COUNT(DISTINCT specimen_id) AS n_specimens,
            COUNT(*) AS n_results,
            COUNT(DISTINCT organism_taxid) AS n_taxa,
            COUNT(DISTINCT antibiotic_atc) AS n_abx,
            COUNT(DISTINCT specimen_id) FILTER (
                WHERE specimen_type = 'BLOOD' AND sir_classification IS NOT NULL
            ) AS n_blood_with_ast,
            COUNT(DISTINCT specimen_id) FILTER (WHERE specimen_type = 'BLOOD') AS n_blood_total,
            COUNT(DISTINCT specimen_id) FILTER (WHERE organism_taxid IS NOT NULL) AS n_with_species_id
        FROM isolate_events
        WHERE facility_id = %s
          AND collection_date >= %s AND collection_date < %s;
    """
    with get_cursor() as cur:
        cur.execute(sql, (facility_id, period_start, period_end))
        r = cur.fetchone()

    n_blood_total = r["n_blood_total"] or 0
    n_specimens = r["n_specimens"] or 0
    pct_blood_ast = (
        100 * (r["n_blood_with_ast"] or 0) / n_blood_total if n_blood_total else 0.0
    )
    pct_species = (
        100 * (r["n_with_species_id"] or 0) / n_specimens if n_specimens else 0.0
    )
    return QualityIndicators(
        facility_id=facility_id,
        year=year,
        pct_blood_with_ast=round(pct_blood_ast, 2),
        pct_isolates_species_id=round(pct_species, 2),
        n_unique_specimens=n_specimens,
        n_isolate_results=r["n_results"] or 0,
        n_organism_taxa=r["n_taxa"] or 0,
        n_antibiotics_tested=r["n_abx"] or 0,
    )
