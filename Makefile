# AMR Sentinel — common operations.
# Usage:  make <target>

.PHONY: help bootstrap up down restart logs ps test test-fast \
        sample-data load-data train smoke clean nuke

help:
	@echo "Common targets:"
	@echo "  bootstrap   — full one-command boot: up + topics + Neo4j + data + train + smoke"
	@echo "  up          — docker compose up -d"
	@echo "  down        — stop containers (preserve volumes)"
	@echo "  restart     — down + up"
	@echo "  logs        — tail logs from all services"
	@echo "  ps          — list running containers"
	@echo "  test        — run all unit tests"
	@echo "  test-fast   — only fast tests (skip slow algorithm tests)"
	@echo "  sample-data — generate synthetic isolate CSV"
	@echo "  load-data   — load synthetic CSV directly into TimescaleDB"
	@echo "  train       — train the resistance predictor"
	@echo "  smoke       — run the end-to-end smoke test"
	@echo "  clean       — remove generated data (synthetic CSVs, model artifacts)"
	@echo "  nuke        — clean + drop all docker volumes (DESTRUCTIVE)"

bootstrap:
	bash scripts/bootstrap.sh

up:
	docker compose up -d

down:
	docker compose down

restart: down up

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps

test:
	pytest

test-fast:
	pytest -m "not slow"

sample-data:
	python scripts/generate_sample_data.py

load-data:
	bash scripts/load_sample_data.sh

train:
	cd services && PYTHONPATH=. python -m intelligence.ml.train

smoke:
	python scripts/smoke_test.py

clean:
	rm -rf data/sample_data/synthetic_*.csv data/models/*.joblib

nuke: clean
	docker compose down -v
