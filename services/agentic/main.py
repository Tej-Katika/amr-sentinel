"""Agentic FastAPI service.

POST /query — main entry point for clinical questions.
GET  /health
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime

import psycopg2
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from .agent import run_agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("agentic")

app = FastAPI(
    title="AMR Sentinel — Agentic",
    version="0.1.0",
    description="Clinical stewardship assistant powered by Claude tool-calling.",
)


class QueryRequest(BaseModel):
    query: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "agentic"}


@app.post("/query")
async def query(req: QueryRequest,
                x_facility_id: str = Header(..., alias="X-Facility-Id"),
                x_user_id: str = Header(..., alias="X-User-Id")) -> dict:
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Empty query")

    response = await run_agent(req.query, facility_id=x_facility_id, user_id=x_user_id)
    _audit(req.query, x_facility_id, x_user_id, response)

    return {
        "recommendation": response.recommendation,
        "tools_called": response.tools_called,
        "confidence_score": response.confidence_score,
        "data_provenance": response.data_provenance,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


def _audit(query: str, facility_id: str, user_id: str, response) -> None:
    """Persist the recommendation log. Best-effort; never raise to the client.

    user_id is a UUID for real authenticated users (from the JWT) and a free-form
    string for service callers (smoke test, eval harness). We store the UUID in
    user_id and the raw string in actor_label so neither gets lost.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return

    uuid_user, label = _split_actor(user_id)
    try:
        with psycopg2.connect(db_url) as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO recommendation_log (
                    facility_id, user_id, actor_label, query_text, tools_called,
                    tool_results, recommendation, confidence_score, data_provenance
                ) VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s::jsonb);
                """,
                (
                    facility_id,
                    uuid_user,
                    label,
                    query,
                    json.dumps(response.tools_called),
                    json.dumps(response.tool_results, default=str),
                    response.recommendation,
                    response.confidence_score,
                    json.dumps(response.data_provenance, default=str),
                ),
            )
    except Exception:
        log.exception("Audit log failed")


def _split_actor(value: str) -> tuple[str | None, str | None]:
    """Returns (uuid_user_id_or_none, actor_label).

    If `value` parses as a UUID, it goes into user_id and label is None.
    Otherwise the raw string goes into actor_label so we never silently drop it.
    """
    import uuid
    try:
        return str(uuid.UUID(value)), None
    except (ValueError, AttributeError):
        if value:
            log.debug("Non-UUID actor recorded as label: %s", value)
        return None, value or None
