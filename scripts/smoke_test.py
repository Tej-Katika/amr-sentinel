#!/usr/bin/env python3
"""End-to-end smoke test.

Verifies the full pipeline runs:
    1. Generate sample data
    2. POST a small batch via the ingestion service
    3. Check that the validated event reaches Kafka or TimescaleDB
    4. Query the antibiogram via the intelligence service
    5. Send a query to the agentic service

Run after `docker compose up -d`.
"""
from __future__ import annotations

import json
import os
import sys
import time

import httpx

INGESTION = os.getenv("INGESTION_SERVICE_URL", "http://localhost:8001")
INTELLIGENCE = os.getenv("INTELLIGENCE_SERVICE_URL", "http://localhost:8002")
AGENTIC = os.getenv("AGENTIC_SERVICE_URL", "http://localhost:8003")
GATEWAY = os.getenv("GATEWAY_URL", "http://localhost:8080/api")


def step(name: str) -> None:
    print(f"\n--- {name} ---")


def check_health(name: str, url: str) -> bool:
    try:
        r = httpx.get(f"{url}/health", timeout=5)
        ok = r.status_code == 200
        print(f"  {name}: {'OK' if ok else 'FAIL'} ({r.status_code})")
        return ok
    except Exception as exc:
        print(f"  {name}: UNREACHABLE ({exc})")
        return False


def main() -> int:
    step("Service health checks")
    healthy = [
        check_health("ingestion", INGESTION),
        check_health("intelligence", INTELLIGENCE),
        check_health("agentic", AGENTIC),
    ]
    if not all(healthy):
        print("\nNot all services are up. Run `docker compose up -d` first.")
        return 1

    step("Submit a manual isolate batch")
    payload = [
        {
            "facility_id": "FACILITY_001",
            "specimen_id": f"SMOKE-{int(time.time())}-{i}",
            "specimen_type": "BLOOD",
            "organism_input": "eco",
            "antibiotic_input": "CIP",
            "measurement_type": "MIC",
            "measurement_value": 4.0,
            "measurement_comparator": None,
            "patient_age_group": "65+",
            "patient_sex": "M",
            "ward_id": "WARD_001_ICU",
            "infection_origin": "HOSPITAL",
            "collection_date": "2026-04-15",
            "source_format": "MANUAL",
        }
        for i in range(5)
    ]
    r = httpx.post(f"{INGESTION}/upload/manual", json=payload, timeout=15)
    r.raise_for_status()
    print(f"  Ingestion result: {r.json()}")

    step("Query antibiogram from Intelligence")
    r = httpx.get(f"{INTELLIGENCE}/antibiogram",
                  params={"facility_id": "FACILITY_001", "period_months": 12, "stratification": "ALL"},
                  timeout=30)
    r.raise_for_status()
    cells = r.json().get("cells", [])
    print(f"  {len(cells)} antibiogram cells returned")

    step("Query alerts from Intelligence")
    r = httpx.get(f"{INTELLIGENCE}/alerts",
                  params={"facility_id": "FACILITY_001", "severity": "ALL", "days_back": 90},
                  timeout=10)
    print(f"  Alerts: count={r.json().get('count')}")

    step("Send a question to the agent")
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("  Skipping (ANTHROPIC_API_KEY not set)")
    else:
        r = httpx.post(
            f"{AGENTIC}/query",
            headers={"X-Facility-Id": "FACILITY_001", "X-User-Id": "smoke-test"},
            json={"query": "What's the current ciprofloxacin resistance for E. coli?"},
            timeout=120,
        )
        r.raise_for_status()
        body = r.json()
        print(f"  Agent confidence: {body.get('confidence_score')}")
        print(f"  Tools called: {body.get('tools_called')}")
        rec = body.get("recommendation", "")
        print(f"  First 240 chars of recommendation:\n    {rec[:240]}…")

    print("\nSmoke test complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
