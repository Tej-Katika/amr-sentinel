"""GLASS SAMPLE file generator.

Demographic breakdown of specimens: age groups, sex, specimen types.
"""
from __future__ import annotations

import csv
import io
from datetime import date

from ..db import get_cursor


GLASS_SAMPLE_COLUMNS = [
    "country_iso3", "facility_id", "year",
    "specimen_type", "patient_age_group", "patient_sex",
    "infection_origin", "n_specimens",
]


def generate(facility_id: str, year: int) -> str:
    period_start = date(year, 1, 1)
    period_end = date(year + 1, 1, 1)

    sql = """
        SELECT f.country_iso3, i.facility_id,
               EXTRACT(YEAR FROM i.collection_date)::int AS year,
               i.specimen_type, i.patient_age_group, i.patient_sex,
               i.infection_origin,
               COUNT(DISTINCT i.specimen_id) AS n_specimens
        FROM isolate_events i
        JOIN facilities f ON f.facility_id = i.facility_id
        WHERE i.facility_id = %s
          AND i.collection_date >= %s AND i.collection_date < %s
        GROUP BY f.country_iso3, i.facility_id, year,
                 i.specimen_type, i.patient_age_group, i.patient_sex,
                 i.infection_origin;
    """
    with get_cursor() as cur:
        cur.execute(sql, (facility_id, period_start, period_end))
        rows = cur.fetchall()

    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=GLASS_SAMPLE_COLUMNS)
    writer.writeheader()
    for r in rows:
        writer.writerow({col: r[col] for col in GLASS_SAMPLE_COLUMNS})
    return out.getvalue()
