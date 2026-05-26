# AMR Sentinel

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

An open-source, event-driven antimicrobial resistance (AMR) surveillance and clinical stewardship platform. AMR Sentinel ingests antimicrobial susceptibility test data from hospital microbiology labs in real time, classifies isolates against EUCAST and CLSI breakpoints, runs streaming outbreak detection (CUSUM and BOCPD), and exposes an LLM-assisted clinical stewardship interface for empiric therapy recommendations grounded in local resistance patterns.

The platform is designed to fill a specific gap in the AMR ecosystem: hospitals generate AST data daily but it sits in legacy desktop tools (typically WHONET), reports are compiled manually weeks later, and no open-source tool integrates surveillance, stewardship, and WHO GLASS reporting in one place.

> **Project status**: phase-1 implementation. Core infrastructure, ingestion, classification, and surveillance layers are functional with synthetic data. The agentic stewardship layer and frontend dashboard are in active development. Not production-ready; not for clinical use.

## Table of contents

- [Architecture](#architecture)
- [Quickstart](#quickstart)
- [Repository layout](#repository-layout)
- [Development](#development)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [Security](#security)
- [Citation](#citation)
- [License](#license)

## Architecture

Four-layer event-driven architecture:

```
Layer 1 — Data ingestion         Python/FastAPI → Kafka → TimescaleDB
                                 (parsers: WHONET, CSV, FHIR R4)
        │
        ▼   Kafka events
Layer 2 — Intelligence engine    Classification (breakpoints + AWaRe)
                                 Surveillance (CUSUM + BOCPD + clusters)
                                 Prediction + Neo4j knowledge graph
        │
        ▼   Structured results
Layer 3 — Agentic stewardship    FastAPI + Claude tool-calling
        │
        ▼   Recommendations
Layer 4 — Reporting              Spring Boot gateway + React dashboard
                                 GLASS-compliant exports
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design document, including data-flow diagrams, technology choices, and rationale.

## Quickstart

The full local stack runs in Docker Compose. Requires Docker Desktop and ~8 GB of free RAM.

```bash
# 1. Bring up the full stack (Kafka, Schema Registry, TimescaleDB, Neo4j, Redis, services)
docker compose up -d

# 2. Apply database schema (only if not auto-applied by the container)
./scripts/setup_timescaledb.sh

# 3. Create Kafka topics
./scripts/setup_kafka_topics.sh

# 4. Bootstrap the Neo4j knowledge graph
./scripts/setup_neo4j.sh

# 5. Generate and load synthetic isolate data
python scripts/generate_sample_data.py
./scripts/load_sample_data.sh

# 6. Set the Anthropic API key for the agentic layer (optional for non-LLM features)
export ANTHROPIC_API_KEY=sk-ant-...

# 7. End-to-end smoke test
python scripts/smoke_test.py
```

The dashboard is available at `http://localhost:3000`. Seed login: `demo@amrsentinel.org` / `demo_password`.

For a lightweight stack without Neo4j or the agentic layer, use `docker compose -f docker-compose.dev.yml up -d`.

Common operations are wrapped in the `Makefile`:

```bash
make help          # list targets
make bootstrap     # one-command boot
make test          # run unit tests
make smoke         # end-to-end smoke test
```

## Repository layout

```
amr-sentinel/
├── services/
│   ├── ingestion/        Python/FastAPI parsers + Kafka producer
│   ├── intelligence/     Breakpoints, surveillance, ML, knowledge graph
│   ├── agentic/          Claude tool-calling clinical assistant
│   └── gateway/          Java/Spring Boot API gateway
├── frontend/             React 18 + TypeScript dashboard (Vite)
├── data/                 Reference data (breakpoints, AWaRe, CARD, seed data)
├── scripts/              Setup, sample data, smoke test, download utilities
├── docs/                 Architecture documentation
├── docker-compose.yml    Full local development stack
├── docker-compose.dev.yml Lightweight subset (no Neo4j, no agentic)
└── Makefile              Common operations
```

## Development

### Prerequisites

- Python 3.12+
- Node.js 20+ (for the frontend)
- Java 21+ (for the gateway)
- Docker Desktop with Docker Compose v2
- ~8 GB of free RAM for the full stack

### Running tests

```bash
pip install -r requirements-dev.txt
pytest                          # all tests
pytest -m "not slow"            # fast tests only
pytest services/intelligence    # one service
```

### Environment configuration

Copy `.env.example` to `.env` and fill in local values. The example file contains development defaults safe for a local Docker Compose setup. Production deployments must replace every secret in `.env.example`.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — full system design, data flows, technology choices
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — how to file issues, set up a dev environment, and submit pull requests
- [`SECURITY.md`](SECURITY.md) — security policy and vulnerability reporting
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) — community standards

## Contributing

Contributions are welcome. Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a pull request. By participating in this project you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).

## Security

This project handles healthcare-adjacent data. If you discover a security vulnerability, please follow the responsible disclosure process described in [`SECURITY.md`](SECURITY.md). Please do not file public issues for security problems.

## Citation

If you use AMR Sentinel in academic work, please cite it using the metadata in [`CITATION.cff`](CITATION.cff). GitHub's "Cite this repository" widget will surface a formatted citation automatically.

## License

Apache License 2.0 — see [`LICENSE`](LICENSE).
