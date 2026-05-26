"""FastAPI application for the ingestion service.

Endpoints:
    POST /upload/whonet        Upload a WHONET .txt/.csv export
    POST /upload/csv           Upload a generic CSV (with mapping)
    POST /upload/fhir          Upload a FHIR DiagnosticReport bundle (JSON)
    POST /upload/manual        Submit raw isolates as JSON
    GET  /health
"""
from __future__ import annotations

import json
import logging

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from .models import RawIsolate
from .parsers.csv_mapper import parse_csv
from .parsers.fhir_r4 import parse_fhir_bundle
from .parsers.whonet import parse_whonet
from .pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("ingestion")

app = FastAPI(
    title="AMR Sentinel — Ingestion",
    version="0.1.0",
    description="Parses lab data (WHONET / CSV / FHIR), validates, de-identifies, and publishes to Kafka.",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ingestion"}


@app.post("/upload/whonet")
async def upload_whonet(
    file: UploadFile = File(...),
    facility_id: str | None = Form(None),
) -> dict:
    text = (await file.read()).decode("utf-8", errors="replace")
    raws = list(parse_whonet(text, default_facility_id=facility_id))
    if not raws:
        raise HTTPException(status_code=400, detail="No isolates parsed from WHONET file")
    result = run_pipeline(raws)
    return result.as_summary()


@app.post("/upload/csv")
async def upload_csv(
    file: UploadFile = File(...),
    mapping_json: str = Form(..., description="Column-mapping config as JSON string"),
) -> dict:
    text = (await file.read()).decode("utf-8", errors="replace")
    try:
        mapping = json.loads(mapping_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid mapping JSON: {exc}") from exc

    raws = list(parse_csv(text, mapping))
    if not raws:
        raise HTTPException(status_code=400, detail="No isolates parsed from CSV file")
    result = run_pipeline(raws)
    return result.as_summary()


@app.post("/upload/fhir")
async def upload_fhir(payload: dict, facility_id: str | None = None) -> dict:
    raws = list(parse_fhir_bundle(payload, default_facility_id=facility_id))
    if not raws:
        raise HTTPException(status_code=400, detail="No isolates parsed from FHIR bundle")
    result = run_pipeline(raws)
    return result.as_summary()


@app.post("/upload/manual")
async def upload_manual(payload: list[RawIsolate]) -> dict:
    if not payload:
        raise HTTPException(status_code=400, detail="Empty payload")
    result = run_pipeline(payload)
    return result.as_summary()
