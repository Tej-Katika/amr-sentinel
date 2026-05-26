"""GLASS RIS file generator.

WHO GLASS RIS (Resistance) file: one row per organism-antibiotic combination
per facility per period, with counts of S, I, R, total tested.

Output is CSV with the GLASS standard column set.
"""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta

from ..db import get_cursor


GLASS_RIS_COLUMNS = [
    "country_iso3", "facility_id", "year", "specimen_type",
    "organism_taxid", "organism_name",
    "antibiotic_atc", "antibiotic_name",
    "n_susceptible", "n_intermediate", "n_resistant", "n_tested",
    "breakpoint_standard",
]


def generate(facility_id: str, year: int) -> str:
    """Build a GLASS RIS CSV for a facility-year."""
    period_start = date(year, 1, 1)
    period_end = date(year + 1, 1, 1)

    sql = """
        WITH first_isolates AS (
            SELECT DISTINCT ON (i.facility_id, i.specimen_id, i.organism_taxid, i.antibiotic_atc)
                f.country_iso3,
                i.facility_id,
                EXTRACT(YEAR FROM i.collection_date)::int AS year,
                i.specimen_type,
                i.organism_taxid,
                i.organism_name,
                i.antibiotic_atc,
                i.antibiotic_name,
                i.sir_classification,
                i.breakpoint_standard
            FROM isolate_events i
            JOIN facilities f ON f.facility_id = i.facility_id
            WHERE i.facility_id = %s
              AND i.collection_date >= %s
              AND i.collection_date <  %s
              AND i.sir_classification IS NOT NULL
            ORDER BY i.facility_id, i.specimen_id, i.organism_taxid, i.antibiotic_atc, i.collection_date ASC
        )
        SELECT country_iso3, facility_id, year, specimen_type,
               organism_taxid, organism_name,
               antibiotic_atc, antibiotic_name,
               COUNT(*) FILTER (WHERE sir_classification = 'S') AS n_susceptible,
               COUNT(*) FILTER (WHERE sir_classification = 'I') AS n_intermediate,
               COUNT(*) FILTER (WHERE sir_classification = 'R') AS n_resistant,
               COUNT(*) AS n_tested,
               MIN(breakpoint_standard) AS breakpoint_standard
        FROM first_isolates
        GROUP BY country_iso3, facility_id, year, specimen_type,
                 organism_taxid, organism_name,
                 antibiotic_atc, antibiotic_name;
    """
    with get_cursor() as cur:
        cur.execute(sql, (facility_id, period_start, period_end))
        rows = cur.fetchall()

    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=GLASS_RIS_COLUMNS)
    writer.writeheader()
    for r in rows:
        writer.writerow({col: r[col] for col in GLASS_RIS_COLUMNS})
    return out.getvalue()
