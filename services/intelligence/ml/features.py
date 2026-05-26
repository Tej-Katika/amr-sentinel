"""Feature engineering for the resistance predictor.

Each row in the training set is one isolate. Target = sir_classification == 'R'.
Features:
    - region (WHO region from facility)
    - country_iso3
    - facility_id (encoded as categorical)
    - organism_taxid
    - antibiotic_atc
    - drug_class
    - specimen_type
    - patient_age_group
    - patient_sex
    - ward_type
    - infection_origin
    - year, month
    - facility_baseline_rate (rolling 12-month %R for this organism+abx at this facility)
"""
from __future__ import annotations

import pandas as pd

from ..db import get_conn

CATEGORICAL_FEATURES = [
    "region", "country_iso3", "facility_id",
    "organism_taxid", "antibiotic_atc", "drug_class",
    "specimen_type", "patient_age_group", "patient_sex",
    "ward_type", "infection_origin",
]
NUMERIC_FEATURES = ["year", "month", "facility_baseline_rate"]


def build_training_frame(facility_id: str | None = None) -> pd.DataFrame:
    where = "WHERE i.sir_classification IS NOT NULL"
    params: list = []
    if facility_id:
        where += " AND i.facility_id = %s"
        params.append(facility_id)

    sql = f"""
        WITH base AS (
            SELECT
                i.facility_id,
                f.country_iso3,
                f.region,
                i.organism_taxid,
                i.antibiotic_atc,
                i.drug_class,
                i.specimen_type,
                i.patient_age_group,
                i.patient_sex,
                w.ward_type,
                i.infection_origin,
                i.collection_date,
                EXTRACT(YEAR  FROM i.collection_date)::int  AS year,
                EXTRACT(MONTH FROM i.collection_date)::int  AS month,
                CASE WHEN i.sir_classification = 'R' THEN 1 ELSE 0 END AS resistant
            FROM isolate_events i
            JOIN facilities f ON f.facility_id = i.facility_id
            LEFT JOIN wards w ON w.ward_id = i.ward_id
            {where}
        ),
        baseline AS (
            SELECT facility_id, organism_taxid, antibiotic_atc,
                   AVG(resistant)::float AS facility_baseline_rate
            FROM base
            GROUP BY facility_id, organism_taxid, antibiotic_atc
        )
        SELECT b.*, bl.facility_baseline_rate
        FROM base b
        JOIN baseline bl USING (facility_id, organism_taxid, antibiotic_atc);
    """
    with get_conn() as conn:
        return pd.read_sql(sql, conn, params=params)
