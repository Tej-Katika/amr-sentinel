"""Antibiogram generator following CLSI M39 rules.

Rules:
    1. First isolate per patient per organism per period (M39 §6).
       We approximate "patient" with specimen_id grouping.
    2. Minimum 30 isolates per organism-antibiotic — otherwise omit.
    3. Report %S (susceptible), not %R.
    4. Stratifiable by ward type (ICU vs non-ICU) or specimen type (BLOOD/URINE).
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Optional

from ..db import get_cursor

log = logging.getLogger(__name__)

MIN_ISOLATES = 30


@dataclass
class CellStats:
    organism_taxid: int
    organism_name: str
    antibiotic_atc: str
    antibiotic_name: str
    drug_class: Optional[str]
    n_total: int
    n_susceptible: int
    percent_susceptible: Optional[float]  # None when n_total < MIN_ISOLATES
    aware_category: Optional[str] = None


@dataclass
class Antibiogram:
    facility_id: str
    period_start: str
    period_end: str
    stratification: str
    cells: list[CellStats]
    generated_at: str

    def to_json(self) -> dict:
        return {
            **{k: v for k, v in asdict(self).items() if k != "cells"},
            "cells": [asdict(c) for c in self.cells],
        }


def generate(
    facility_id: str,
    period_start: date,
    period_end: date,
    stratification: str = "ALL",
) -> Antibiogram:
    """Build an antibiogram for the given facility/period/stratification."""
    where, params = _stratification_filter(stratification)
    sql = f"""
        WITH first_isolates AS (
            SELECT DISTINCT ON (facility_id, specimen_id, organism_taxid, antibiotic_atc)
                organism_taxid, organism_name,
                antibiotic_atc, antibiotic_name, drug_class,
                aware_category, sir_classification
            FROM isolate_events
            WHERE facility_id = %s
              AND collection_date >= %s
              AND collection_date <  %s
              AND sir_classification IS NOT NULL
              {where}
            ORDER BY facility_id, specimen_id, organism_taxid, antibiotic_atc, collection_date ASC
        )
        SELECT
            organism_taxid, organism_name,
            antibiotic_atc, antibiotic_name, drug_class,
            MIN(aware_category) AS aware_category,
            COUNT(*) FILTER (WHERE sir_classification = 'S') AS n_susceptible,
            COUNT(*) AS n_total
        FROM first_isolates
        GROUP BY organism_taxid, organism_name,
                 antibiotic_atc, antibiotic_name, drug_class
        ORDER BY organism_name, antibiotic_name;
    """
    args = (facility_id, period_start, period_end + timedelta(days=1), *params)

    with get_cursor() as cur:
        cur.execute(sql, args)
        rows = cur.fetchall()

    cells: list[CellStats] = []
    for r in rows:
        n_total = r["n_total"]
        n_s = r["n_susceptible"]
        pct = round(100 * n_s / n_total, 1) if n_total >= MIN_ISOLATES else None
        cells.append(CellStats(
            organism_taxid=r["organism_taxid"],
            organism_name=r["organism_name"],
            antibiotic_atc=r["antibiotic_atc"],
            antibiotic_name=r["antibiotic_name"],
            drug_class=r["drug_class"],
            n_total=n_total,
            n_susceptible=n_s,
            percent_susceptible=pct,
            aware_category=r["aware_category"],
        ))

    from datetime import datetime
    return Antibiogram(
        facility_id=facility_id,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        stratification=stratification,
        cells=cells,
        generated_at=datetime.utcnow().isoformat() + "Z",
    )


def store(antibiogram: Antibiogram) -> str:
    """Persist the generated antibiogram to TimescaleDB."""
    sql = """
        INSERT INTO antibiograms (facility_id, period_start, period_end, stratification, data)
        VALUES (%s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (facility_id, period_start, period_end, stratification)
        DO UPDATE SET data = EXCLUDED.data, generated_at = NOW()
        RETURNING antibiogram_id;
    """
    with get_cursor(commit=True) as cur:
        cur.execute(sql, (
            antibiogram.facility_id,
            antibiogram.period_start,
            antibiogram.period_end,
            antibiogram.stratification,
            json.dumps(antibiogram.to_json()),
        ))
        return str(cur.fetchone()["antibiogram_id"])


def _stratification_filter(stratification: str) -> tuple[str, tuple]:
    s = stratification.upper()
    if s == "ALL":
        return "", ()
    if s == "ICU":
        return "AND ward_id IN (SELECT ward_id FROM wards WHERE ward_type = 'ICU')", ()
    if s == "NON_ICU":
        return "AND (ward_id IS NULL OR ward_id IN (SELECT ward_id FROM wards WHERE ward_type <> 'ICU'))", ()
    if s == "BLOOD":
        return "AND specimen_type = 'BLOOD'", ()
    if s == "URINE":
        return "AND specimen_type = 'URINE'", ()
    raise ValueError(f"Unknown stratification: {stratification}")
