-- AMR Sentinel TimescaleDB schema
-- Applied automatically by docker-entrypoint-initdb.d on first run.

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- Core Tables
-- ============================================

CREATE TABLE IF NOT EXISTS facilities (
    facility_id     VARCHAR(50) PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    country_iso3    CHAR(3) NOT NULL,
    region          VARCHAR(100),
    facility_type   VARCHAR(20) DEFAULT 'hospital',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS wards (
    ward_id         VARCHAR(50) PRIMARY KEY,
    facility_id     VARCHAR(50) NOT NULL REFERENCES facilities(facility_id),
    name            VARCHAR(100) NOT NULL,
    ward_type       VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS users (
    user_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id     VARCHAR(50) NOT NULL REFERENCES facilities(facility_id),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(20) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- Isolate events hypertable
-- ============================================

CREATE TABLE IF NOT EXISTS isolate_events (
    event_id                UUID DEFAULT gen_random_uuid(),
    facility_id             VARCHAR(50) NOT NULL,
    specimen_id             VARCHAR(100) NOT NULL,
    specimen_type           VARCHAR(20),
    organism_taxid          INT NOT NULL,
    organism_name           VARCHAR(255) NOT NULL,
    gram_stain              VARCHAR(10),
    antibiotic_atc          VARCHAR(10) NOT NULL,
    antibiotic_name         VARCHAR(100) NOT NULL,
    drug_class              VARCHAR(100),
    measurement_type        VARCHAR(4) NOT NULL,
    measurement_value       FLOAT NOT NULL,
    measurement_comparator  VARCHAR(2),
    sir_classification      CHAR(1),
    breakpoint_standard     VARCHAR(10),
    breakpoint_version      VARCHAR(10),
    aware_category          VARCHAR(10),
    patient_age_group       VARCHAR(10),
    patient_sex             CHAR(1),
    ward_id                 VARCHAR(50),
    infection_origin        VARCHAR(20),
    is_first_isolate        BOOLEAN DEFAULT TRUE,
    collection_date         TIMESTAMPTZ NOT NULL,
    ingested_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    classified_at           TIMESTAMPTZ,
    source_format           VARCHAR(20),
    PRIMARY KEY (event_id, collection_date)
);

SELECT create_hypertable('isolate_events', 'collection_date',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_isolate_facility_org
    ON isolate_events (facility_id, organism_taxid);
CREATE INDEX IF NOT EXISTS idx_isolate_facility_abx
    ON isolate_events (facility_id, antibiotic_atc);
CREATE INDEX IF NOT EXISTS idx_isolate_sir
    ON isolate_events (sir_classification);
CREATE INDEX IF NOT EXISTS idx_isolate_ward
    ON isolate_events (ward_id);
CREATE INDEX IF NOT EXISTS idx_isolate_specimen
    ON isolate_events (facility_id, specimen_id);

-- ============================================
-- Continuous aggregates
-- ============================================

CREATE MATERIALIZED VIEW IF NOT EXISTS daily_resistance_rates
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', collection_date) AS day,
    facility_id,
    organism_name,
    organism_taxid,
    antibiotic_name,
    antibiotic_atc,
    drug_class,
    COUNT(*) FILTER (WHERE sir_classification = 'R') AS resistant_count,
    COUNT(*) FILTER (WHERE sir_classification = 'I') AS intermediate_count,
    COUNT(*) FILTER (WHERE sir_classification = 'S') AS susceptible_count,
    COUNT(*) AS total_count
FROM isolate_events
WHERE sir_classification IS NOT NULL
GROUP BY day, facility_id, organism_name, organism_taxid,
         antibiotic_name, antibiotic_atc, drug_class
WITH NO DATA;

SELECT add_continuous_aggregate_policy('daily_resistance_rates',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE);

CREATE MATERIALIZED VIEW IF NOT EXISTS weekly_resistance_rates
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('7 days', collection_date) AS week,
    facility_id,
    organism_name,
    organism_taxid,
    antibiotic_name,
    antibiotic_atc,
    COUNT(*) FILTER (WHERE sir_classification = 'R') AS resistant_count,
    COUNT(*) AS total_count
FROM isolate_events
WHERE sir_classification IS NOT NULL
GROUP BY week, facility_id, organism_name, organism_taxid,
         antibiotic_name, antibiotic_atc
WITH NO DATA;

SELECT add_continuous_aggregate_policy('weekly_resistance_rates',
    start_offset => INTERVAL '14 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- ============================================
-- Surveillance state
-- ============================================

CREATE TABLE IF NOT EXISTS cusum_state (
    id                  SERIAL PRIMARY KEY,
    facility_id         VARCHAR(50) NOT NULL,
    organism_taxid      INT NOT NULL,
    antibiotic_atc      VARCHAR(10) NOT NULL,
    cusum_sum           FLOAT NOT NULL DEFAULT 0,
    baseline_rate       FLOAT NOT NULL,
    reference_value     FLOAT NOT NULL,
    threshold           FLOAT NOT NULL,
    observations_count  INT NOT NULL DEFAULT 0,
    last_reset_at       TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (facility_id, organism_taxid, antibiotic_atc)
);

CREATE TABLE IF NOT EXISTS bocpd_state (
    id                  SERIAL PRIMARY KEY,
    facility_id         VARCHAR(50) NOT NULL,
    organism_taxid      INT NOT NULL,
    antibiotic_atc      VARCHAR(10) NOT NULL,
    state_blob          JSONB NOT NULL,
    hazard_rate         FLOAT NOT NULL DEFAULT 0.004,
    max_run_length      INT NOT NULL DEFAULT 500,
    changepoint_prob    FLOAT NOT NULL DEFAULT 0,
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (facility_id, organism_taxid, antibiotic_atc)
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id         VARCHAR(50) NOT NULL,
    organism_taxid      INT NOT NULL,
    organism_name       VARCHAR(255) NOT NULL,
    antibiotic_atc      VARCHAR(10),
    antibiotic_name     VARCHAR(100),
    alert_type          VARCHAR(20) NOT NULL,
    severity            VARCHAR(15) NOT NULL,
    current_rate        FLOAT,
    baseline_rate       FLOAT,
    details             JSONB,
    acknowledged        BOOLEAN DEFAULT FALSE,
    acknowledged_by     UUID REFERENCES users(user_id),
    triggered_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_alerts_facility
    ON alerts (facility_id, triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_severity
    ON alerts (severity, triggered_at DESC);

-- ============================================
-- Stewardship tables
-- ============================================

CREATE TABLE IF NOT EXISTS antibiograms (
    antibiogram_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id         VARCHAR(50) NOT NULL,
    period_start        DATE NOT NULL,
    period_end          DATE NOT NULL,
    stratification      VARCHAR(20) DEFAULT 'ALL',
    data                JSONB NOT NULL,
    generated_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (facility_id, period_start, period_end, stratification)
);

CREATE TABLE IF NOT EXISTS resistance_predictions (
    prediction_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id         VARCHAR(50) NOT NULL,
    organism_taxid      INT NOT NULL,
    antibiotic_atc      VARCHAR(10) NOT NULL,
    predicted_rate      FLOAT NOT NULL,
    confidence_lower    FLOAT,
    confidence_upper    FLOAT,
    shap_values         JSONB,
    model_version       VARCHAR(50) NOT NULL,
    predicted_for       DATE NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (facility_id, organism_taxid, antibiotic_atc, predicted_for, model_version)
);

CREATE TABLE IF NOT EXISTS recommendation_log (
    log_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id         VARCHAR(50) NOT NULL,
    user_id             UUID REFERENCES users(user_id),
    actor_label         VARCHAR(100),                 -- non-UUID actors: smoke test, eval harness, etc.
    query_text          TEXT NOT NULL,
    tools_called        JSONB NOT NULL,
    tool_results        JSONB,
    recommendation      TEXT NOT NULL,
    confidence_score    FLOAT,
    data_provenance     JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- Compression and retention
-- ============================================

SELECT add_compression_policy('isolate_events', INTERVAL '6 months',
    if_not_exists => TRUE);

SELECT add_retention_policy('isolate_events', INTERVAL '5 years',
    if_not_exists => TRUE);
