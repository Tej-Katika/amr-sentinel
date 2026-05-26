#!/usr/bin/env bash
# Load synthetic CSV directly into TimescaleDB (skips Kafka pipeline).
# Useful for spinning up a populated demo without running the full stack.

set -euo pipefail

CSV_PATH="${1:-data/sample_data/synthetic_isolates.csv}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-amrsentinel}"
DB_NAME="${DB_NAME:-amrsentinel}"
PGPASSWORD="${PGPASSWORD:-amrsentinel_dev}"

export PGPASSWORD

if [ ! -f "$CSV_PATH" ]; then
    echo "Sample CSV not found at $CSV_PATH"
    echo "Generate it with: python scripts/generate_sample_data.py"
    exit 1
fi

psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
    \\copy isolate_events (
        event_id, facility_id, specimen_id, specimen_type,
        organism_taxid, organism_name, gram_stain,
        antibiotic_atc, antibiotic_name, drug_class,
        measurement_type, measurement_value, measurement_comparator,
        sir_classification, breakpoint_standard, breakpoint_version,
        aware_category,
        patient_age_group, patient_sex, ward_id, infection_origin,
        is_first_isolate,
        collection_date, ingested_at, classified_at,
        source_format
    ) FROM '$CSV_PATH' CSV HEADER;
"

echo "Loaded sample data from $CSV_PATH"
