#!/usr/bin/env bash
# Apply Neo4j schema + load reference data.
# Run after `docker compose up -d neo4j`.

set -euo pipefail

NEO4J_HOST="${NEO4J_HOST:-localhost}"
NEO4J_PORT="${NEO4J_PORT:-7687}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-amrsentinel_dev}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

# Apply constraints + indexes
if command -v cypher-shell >/dev/null 2>&1; then
    cypher-shell -a "bolt://$NEO4J_HOST:$NEO4J_PORT" -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
        --file "$ROOT/services/intelligence/knowledge_graph/schema.cypher"
else
    docker exec -i amr_neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
        < "$ROOT/services/intelligence/knowledge_graph/schema.cypher"
fi

# Load reference data
cd "$ROOT/services/intelligence"
NEO4J_URI="bolt://$NEO4J_HOST:$NEO4J_PORT" \
NEO4J_USER="$NEO4J_USER" \
NEO4J_PASSWORD="$NEO4J_PASSWORD" \
python -m knowledge_graph.loader

echo "Neo4j schema applied and reference data loaded."
