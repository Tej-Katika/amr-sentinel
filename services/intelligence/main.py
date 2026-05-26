"""Intelligence FastAPI service.

Exposes:
    GET  /health
    GET  /antibiogram?facility_id=&period_months=&stratification=&organism=
    POST /antibiogram/regenerate
    GET  /alerts?facility_id=&severity=&days_back=
    GET  /predictions/resistance?facility_id=&organism=&antibiotic=
    GET  /trends/resistance?facility_id=&organism=&antibiotic=&days=
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Response

from dataclasses import asdict

from .antibiogram.generator import generate, store
from .antibiogram.pdf_export import render_pdf
from .db import get_cursor
from .glass import quality_checker, ris_generator, sample_generator
from .knowledge_graph import queries as kg_queries
from .knowledge_graph.loader import get_driver as get_neo4j_driver
from .ml.resistance_predictor import get_predictor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("intelligence")

app = FastAPI(
    title="AMR Sentinel — Intelligence",
    version="0.1.0",
    description="Classification, surveillance, antibiogram, and prediction service.",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "intelligence"}


@app.get("/antibiogram")
def get_antibiogram(
    facility_id: str,
    period_months: int = Query(12, ge=1, le=60),
    stratification: str = "ALL",
    organism: Optional[str] = None,
) -> dict:
    period_end = date.today()
    period_start = period_end - timedelta(days=30 * period_months)

    sql = """
        SELECT data FROM antibiograms
        WHERE facility_id = %s AND period_start <= %s AND period_end >= %s
              AND stratification = %s
        ORDER BY generated_at DESC LIMIT 1;
    """
    with get_cursor() as cur:
        cur.execute(sql, (facility_id, period_start, period_end, stratification))
        row = cur.fetchone()
    if row:
        data = row["data"]
    else:
        ab = generate(facility_id, period_start, period_end, stratification)
        store(ab)
        data = ab.to_json()

    if organism:
        organism_lc = organism.lower()
        data = {**data, "cells": [c for c in data["cells"] if c["organism_name"].lower() == organism_lc]}
    return data


@app.post("/antibiogram/regenerate")
def regenerate_antibiogram(
    facility_id: str,
    period_months: int = 12,
    stratification: str = "ALL",
) -> dict:
    period_end = date.today()
    period_start = period_end - timedelta(days=30 * period_months)
    ab = generate(facility_id, period_start, period_end, stratification)
    antibiogram_id = store(ab)
    return {"antibiogram_id": antibiogram_id, "cells": len(ab.cells)}


@app.get("/antibiogram/pdf")
def get_antibiogram_pdf(
    facility_id: str,
    period_months: int = 12,
    stratification: str = "ALL",
) -> Response:
    period_end = date.today()
    period_start = period_end - timedelta(days=30 * period_months)
    ab = generate(facility_id, period_start, period_end, stratification)
    pdf = render_pdf(ab)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=antibiogram_{facility_id}.pdf"})


@app.get("/alerts")
def list_alerts(
    facility_id: str,
    severity: str = "ALL",
    days_back: int = Query(30, ge=1, le=365),
) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=days_back)
    where = "WHERE facility_id = %s AND triggered_at >= %s"
    params: list = [facility_id, cutoff]
    if severity.upper() != "ALL":
        where += " AND severity = %s"
        params.append(severity.upper())

    sql = f"""
        SELECT alert_id, facility_id, organism_taxid, organism_name,
               antibiotic_atc, antibiotic_name, alert_type, severity,
               current_rate, baseline_rate, details,
               acknowledged, acknowledged_by, triggered_at, resolved_at
        FROM alerts
        {where}
        ORDER BY triggered_at DESC LIMIT 200;
    """
    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = [
            {**r, "alert_id": str(r["alert_id"]), "triggered_at": r["triggered_at"].isoformat()}
            for r in cur.fetchall()
        ]
    return {"alerts": rows, "count": len(rows)}


@app.get("/trends/resistance")
def resistance_trend(
    facility_id: str,
    organism: str,
    antibiotic: str,
    days: int = Query(180, ge=7, le=730),
) -> dict:
    cutoff = date.today() - timedelta(days=days)
    sql = """
        SELECT day::date AS day,
               resistant_count,
               total_count,
               CASE WHEN total_count > 0 THEN resistant_count::float / total_count ELSE NULL END AS rate
        FROM daily_resistance_rates
        WHERE facility_id = %s
          AND organism_name = %s
          AND antibiotic_name = %s
          AND day >= %s
        ORDER BY day ASC;
    """
    with get_cursor() as cur:
        cur.execute(sql, (facility_id, organism, antibiotic, cutoff))
        rows = [
            {"day": r["day"].isoformat(), "rate": r["rate"], "n": r["total_count"]}
            for r in cur.fetchall()
        ]
    return {"facility_id": facility_id, "organism": organism, "antibiotic": antibiotic, "series": rows}


@app.get("/predictions/resistance")
def get_prediction(facility_id: str, organism: str, antibiotic: str) -> dict:
    sql = """
        SELECT predicted_rate, confidence_lower, confidence_upper,
               shap_values, model_version, predicted_for, created_at
        FROM resistance_predictions
        WHERE facility_id = %s
          AND organism_taxid = (SELECT MIN(organism_taxid) FROM isolate_events WHERE organism_name = %s)
          AND antibiotic_atc = (SELECT MIN(antibiotic_atc) FROM isolate_events WHERE antibiotic_name = %s)
        ORDER BY created_at DESC LIMIT 1;
    """
    with get_cursor() as cur:
        cur.execute(sql, (facility_id, organism, antibiotic))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No prediction available for this combination")
    return {
        "facility_id": facility_id,
        "organism": organism,
        "antibiotic": antibiotic,
        "predicted_rate": row["predicted_rate"],
        "confidence_lower": row["confidence_lower"],
        "confidence_upper": row["confidence_upper"],
        "shap_values": row["shap_values"],
        "model_version": row["model_version"],
        "predicted_for": row["predicted_for"].isoformat() if row["predicted_for"] else None,
    }


@app.get("/glass/ris.csv")
def glass_ris(facility_id: str, year: int) -> Response:
    csv_text = ris_generator.generate(facility_id, year)
    return Response(content=csv_text, media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=glass_ris_{facility_id}_{year}.csv"})


@app.get("/glass/sample.csv")
def glass_sample(facility_id: str, year: int) -> Response:
    csv_text = sample_generator.generate(facility_id, year)
    return Response(content=csv_text, media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=glass_sample_{facility_id}_{year}.csv"})


@app.get("/glass/quality")
def glass_quality(facility_id: str, year: int) -> dict:
    return asdict(quality_checker.compute(facility_id, year))


@app.get("/kg/organism/{organism}/genes")
def kg_organism_genes(organism: str, facility_id: Optional[str] = None) -> dict:
    driver = get_neo4j_driver()
    try:
        return {"organism": organism, "genes": kg_queries.organism_genes(driver, organism, facility_id)}
    finally:
        driver.close()


@app.get("/kg/organism/{organism}/profile")
def kg_organism_profile(organism: str, facility_id: str) -> dict:
    driver = get_neo4j_driver()
    try:
        return {
            "organism": organism,
            "facility_id": facility_id,
            "profile": kg_queries.organism_resistance_profile(driver, organism, facility_id),
        }
    finally:
        driver.close()


@app.post("/predict/resistance")
def predict_resistance(payload: dict) -> dict:
    """Predict P(resistant) for an organism+antibiotic+context combination.

    Required fields:
        organism_taxid, antibiotic_atc, drug_class, facility_id, country_iso3,
        region, specimen_type, patient_age_group, patient_sex, ward_type,
        infection_origin, year, month, facility_baseline_rate
    """
    predictor = get_predictor()
    if predictor.pipeline is None:
        raise HTTPException(status_code=503, detail="No model trained yet — run `python -m ml.train`")
    result = predictor.predict(payload)
    result["shap_values"] = predictor.shap_values(payload)
    return result


@app.get("/facility/{facility_id}/summary")
def facility_summary(facility_id: str) -> dict:
    """Quick stats for the dashboard landing page."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM isolate_events WHERE facility_id = %s",
            (facility_id,),
        )
        total_isolates = cur.fetchone()["n"]
        cur.execute(
            """SELECT severity, COUNT(*) AS n
               FROM alerts
               WHERE facility_id = %s AND triggered_at >= NOW() - INTERVAL '30 days'
               GROUP BY severity""",
            (facility_id,),
        )
        alerts_by_severity = {r["severity"]: r["n"] for r in cur.fetchall()}
    return {
        "facility_id": facility_id,
        "total_isolates": total_isolates,
        "alerts_30d": alerts_by_severity,
    }
