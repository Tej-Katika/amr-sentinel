#!/usr/bin/env bash
# Apply TimescaleDB schema + seed data to a running database.
# Used when not relying on docker-entrypoint-initdb.d (e.g., RDS).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-amrsentinel}"
DB_NAME="${DB_NAME:-amrsentinel}"
PGPASSWORD="${PGPASSWORD:-amrsentinel_dev}"

export PGPASSWORD

for f in "${SCRIPT_DIR}/ddl"/*.sql; do
    echo "Applying $(basename "$f")..."
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -f "$f"
done

echo "TimescaleDB schema applied successfully."
