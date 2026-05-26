#!/usr/bin/env bash
# One-command bootstrap: bring everything up, populate it, and run a smoke test.
#
# Steps:
#   1. docker compose up
#   2. wait for Kafka and TimescaleDB to be reachable
#   3. create Kafka topics
#   4. apply Neo4j schema + load reference data
#   5. generate + load synthetic isolate data
#   6. train an XGBoost resistance model
#   7. run smoke_test.py
#
# Idempotent — safe to re-run. Preserves existing volumes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

# ----- helpers ---------------------------------------------------------------

log() { printf "\033[1;36m[bootstrap]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[bootstrap]\033[0m %s\n" "$*" >&2; }
fail() { printf "\033[1;31m[bootstrap]\033[0m %s\n" "$*" >&2; exit 1; }

require() {
    command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

wait_for_tcp() {
    local host="$1" port="$2" name="$3" attempts="${4:-60}"
    log "Waiting for $name at $host:$port..."
    for _ in $(seq 1 "$attempts"); do
        if (echo > /dev/tcp/"$host"/"$port") >/dev/null 2>&1; then
            log "  $name is up."
            return 0
        fi
        sleep 2
    done
    fail "$name did not come up within $((attempts*2)) seconds"
}

wait_for_http() {
    local url="$1" name="$2" attempts="${3:-60}"
    log "Waiting for $name at $url..."
    for _ in $(seq 1 "$attempts"); do
        if curl -fsS -o /dev/null "$url" 2>/dev/null; then
            log "  $name is up."
            return 0
        fi
        sleep 2
    done
    fail "$name did not become healthy within $((attempts*2)) seconds"
}

# ----- preflight -------------------------------------------------------------

require docker
require curl

if [ ! -f .env ] && [ -f .env.example ]; then
    cp .env.example .env
    warn ".env did not exist — copied from .env.example. Edit it to set ANTHROPIC_API_KEY."
fi

# ----- step 1: bring everything up -------------------------------------------

log "Step 1/7: docker compose up -d"
docker compose up -d

# ----- step 2: wait for infra ------------------------------------------------

log "Step 2/7: wait for infrastructure"
wait_for_tcp localhost 29092 Kafka
wait_for_tcp localhost 5432  TimescaleDB
wait_for_tcp localhost 7687  Neo4j 90

# ----- step 3: kafka topics --------------------------------------------------

log "Step 3/7: create Kafka topics"
bash "$SCRIPT_DIR/setup_kafka_topics.sh"

# ----- step 4: neo4j schema + reference data --------------------------------

log "Step 4/7: load Neo4j schema and reference data"
if bash "$SCRIPT_DIR/setup_neo4j.sh"; then
    log "  Neo4j ready."
else
    warn "Neo4j setup failed; skipping (KG-dependent features may not work)."
fi

# ----- step 5: synthetic data ------------------------------------------------

log "Step 5/7: generate + load synthetic isolates"
if [ ! -f data/sample_data/synthetic_isolates.csv ]; then
    python scripts/generate_sample_data.py
fi
bash "$SCRIPT_DIR/load_sample_data.sh" || warn "Sample data load failed (probably already loaded)"

# ----- step 6: ml training ---------------------------------------------------

log "Step 6/7: train resistance predictor"
(cd services && PYTHONPATH=. python -m intelligence.ml.train) \
    || warn "ML training failed; the /predict endpoint will return 503 until a model exists."

# ----- step 7: smoke test ----------------------------------------------------

log "Step 7/7: wait for application services + run smoke test"
wait_for_http http://localhost:8001/health "ingestion service"  90
wait_for_http http://localhost:8002/health "intelligence service" 90
wait_for_http http://localhost:8003/health "agentic service"   90

python scripts/smoke_test.py

log ""
log "Done. Dashboard: http://localhost:3000  (login demo@amrsentinel.org / demo_password)"
log "API gateway:    http://localhost:8080/api/health"
