# AMR Sentinel v2 — Complete Architecture, Infrastructure & Implementation Guide

*Version 2.0 | April 2026 | Tej Katika*

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Layer 1 — Event-Driven Data Ingestion](#2-layer-1--event-driven-data-ingestion)
3. [Layer 2 — Intelligence Engine](#3-layer-2--intelligence-engine)
4. [Layer 3 — Agentic Stewardship Layer](#4-layer-3--agentic-stewardship-layer)
5. [Layer 4 — Reporting, Dashboards & Integration](#5-layer-4--reporting-dashboards--integration)
6. [Infrastructure & Deployment](#6-infrastructure--deployment)
7. [Data Flow — End to End](#7-data-flow--end-to-end)
8. [Complete Tech Stack Summary](#8-complete-tech-stack-summary)

---

## 1. System Overview

### What AMR Sentinel Is

AMR Sentinel is an open-source, event-driven, agentic antimicrobial resistance surveillance and clinical stewardship intelligence platform. It is designed to solve a specific problem: hospitals generate antimicrobial susceptibility test (AST) data every day from their microbiology labs, but that data sits in legacy desktop software (WHONET), gets manually compiled into reports weeks later, and never feeds back into real-time clinical prescribing decisions.

### The Four-Layer Architecture

The system is organized into four distinct layers, each with a clear responsibility:

- **Layer 1 — Data Ingestion**: Accepts lab data from multiple source formats, validates it, serializes it into a typed event schema, and publishes it to an event bus. Think of this as the "ears" of the system.
- **Layer 2 — Intelligence Engine**: Processes every event through classification (breakpoint → SIR), surveillance (outbreak detection), and prediction (ML resistance forecasting). This is the "brain."
- **Layer 3 — Agentic Stewardship**: An LLM-powered tool-calling layer that synthesizes outputs from Layer 2 into natural language clinical decision support. This is the "voice."
- **Layer 4 — Reporting & Integration**: Dashboards, GLASS-compliant exports, REST/GraphQL APIs, webhook notifications, and PDF reports. This is the "output."

### Why Event-Driven

The v1 architecture was batch-oriented — files uploaded, parsed, loaded into a database, then analyzed. This fails for three reasons:

1. **Latency**: Batch processing means outbreak detection runs on yesterday's data. A CUSUM alert at 3pm about a resistance spike from 8am is too late.
2. **Coupling**: Every component depends on the same database and the same batch schedule. Adding a new analytical module requires modifying the batch pipeline.
3. **Scalability**: A single facility generating 200 isolates/day is fine as batch. A national surveillance network with 500 facilities generating 100,000 isolates/day is not.

The v2 event-driven architecture solves all three. Apache Kafka decouples producers (parsers) from consumers (breakpoint engine, CUSUM, ML predictor). Each consumer processes events independently, at its own pace, and can be scaled horizontally by adding consumer instances.

---

## 2. Layer 1 — Event-Driven Data Ingestion

### Purpose

Accept raw lab data from any source format, validate it, de-identify it, serialize it to a strict typed schema, and publish it as an event to the Kafka bus. Every downstream component receives data exclusively through Kafka — there is no shared database at the ingestion layer.

### Components

#### 2.1 WHONET Parser (Python/FastAPI)

**Why we use it**: WHONET is the world's most widely used AMR surveillance software, deployed in 2,300+ labs across 130+ countries. Any platform that can't ingest WHONET data is irrelevant to 90% of global AMR surveillance.

**How it works**: WHONET exports data in two formats:

1. **Tab-delimited text files** (.txt) — Each row is one isolate-antibiotic test result. Columns include: LAB_ID (laboratory identifier), SPEC_NUM (specimen number), SPEC_TYPE (specimen type code like "bl" for blood, "ur" for urine), ORGANISM (organism code from WHONET's taxonomy), various antibiotic columns (each containing the raw MIC or disk zone value). The column names follow WHONET's internal coding system — e.g., "AMP_ND10" means Ampicillin tested by disk diffusion with a 10µg disk.

2. **Configuration files** (.bac) — Define the mapping between WHONET codes and standard taxonomies. For example, "eco" maps to *Escherichia coli*, "sau" maps to *Staphylococcus aureus*.

The parser reads these files, maps organism codes to NCBI Taxonomy IDs (the universal standard), maps antibiotic codes to ATC (Anatomical Therapeutic Chemical) codes, extracts the measurement type (MIC in µg/mL or disk diffusion zone diameter in mm), and emits one event per isolate-antibiotic combination.

**Implementation detail**: The parser uses a configuration-driven mapping table (JSON/YAML) that maps WHONET column names to standardized internal field names. This mapping is versioned — when WHONET updates their export format (which happens occasionally), you update the mapping file, not the parser code.

```python
# Conceptual structure of a parsed WHONET event
{
    "source_format": "WHONET",
    "facility_id": "HOSP_001",
    "specimen_id": "SP-2026-04-30-0042",
    "specimen_type": "BLOOD",
    "organism_code": "eco",
    "organism_ncbi_taxid": 562,
    "organism_name": "Escherichia coli",
    "antibiotic_whonet_code": "CIP",
    "antibiotic_atc_code": "J01MA02",
    "antibiotic_name": "Ciprofloxacin",
    "measurement_type": "MIC",
    "measurement_value": 4.0,
    "measurement_unit": "ug/mL",
    "patient_age_group": "ADULT",
    "patient_sex": "M",
    "ward": "ICU",
    "collection_date": "2026-04-30",
    "infection_origin": "HOSPITAL",
    "ingested_at": "2026-04-30T14:23:07Z"
}
```

#### 2.2 HL7 FHIR R4 Parser (Python/FastAPI)

**Why we use it**: Modern hospital information systems increasingly use HL7 FHIR (Fast Healthcare Interoperability Resources) for data exchange. The FHIR R4 DiagnosticReport resource is the standard way to represent lab results including AST data. Any hospital with a modern EHR (Epic, Cerner, etc.) can export FHIR resources.

**How it works**: The parser accepts FHIR R4 DiagnosticReport resources (as JSON bundles) via a REST endpoint. It extracts:

- Organism identification from the `result` references pointing to Observation resources with LOINC codes for culture results
- Antibiotic susceptibility from Observation resources with LOINC codes like "18769-0" (Susceptibility panel) containing component Observations for each antibiotic
- MIC values from `valueQuantity` fields, disk zones from `valueQuantity` with mm units
- SIR interpretation from `interpretation` fields (though we re-compute this ourselves through the breakpoint engine for consistency)

**Why we re-compute SIR**: Different labs may use different breakpoint versions (EUCAST 2024 vs CLSI 2025). Our breakpoint engine applies a single consistent standard, so all downstream analytics compare apples to apples.

#### 2.3 Flexible CSV Mapper (Python/FastAPI)

**Why we use it**: Many labs, especially in LMICs (Low and Middle Income Countries), don't use WHONET and don't have FHIR-capable systems. They export data as CSV or Excel files with inconsistent column names — one lab calls it "Bacteria", another calls it "Organism", a third calls it "Pathogen."

**How it works**: The mapper uses a configurable column-mapping definition (YAML) that maps arbitrary source column names to the internal schema. A facility registers its column mapping once (e.g., "Column B = organism, Column D = antibiotic, Column F = MIC value"), and all subsequent uploads from that facility are automatically parsed.

```yaml
# Example facility mapping configuration
facility: HOSP_042
source_format: CSV
column_mappings:
  organism: "Bacteria Name"
  antibiotic: "Drug"
  mic_value: "MIC (ug/ml)"
  specimen_type: "Sample Type"
  collection_date: "Date Collected"
  ward: "Department"
date_format: "DD/MM/YYYY"
organism_taxonomy: "free_text"  # will be matched to NCBI via fuzzy lookup
```

#### 2.4 WGS/FASTQ Ingestion Pipeline (Python)

**Why we use it**: The field is moving beyond phenotypic AST (growing bacteria on plates) toward genomic surveillance. Whole-genome sequencing (WGS) can identify resistance genes directly from DNA, often faster than culture-based methods. Nanopore MinION sequencers are becoming affordable enough for LMIC reference labs.

**How it works**: This module accepts FASTQ files (raw sequencing reads), runs them through an automated pipeline:

1. **Quality control**: fastp for read trimming and quality filtering
2. **Assembly**: SPAdes or Flye for genome assembly (short reads or long reads respectively)
3. **Resistance gene detection**: AMRFinderPlus (NCBI's tool) scans the assembled genome against its curated database of known resistance genes, point mutations, and stress response genes. Output includes gene names, drug classes affected, and confidence scores.
4. **MLST typing**: mlst tool assigns multi-locus sequence type for epidemiological tracking
5. **Event emission**: Genotypic resistance findings are emitted as events to a separate Kafka topic (`isolates.genomic`), which can be correlated with phenotypic events from the same specimen

**Important distinction**: Genotypic data tells you what resistance genes are *present* in the genome. Phenotypic data tells you whether the organism actually *behaves* as resistant in the lab. These don't always agree — a gene might be present but not expressed, or phenotypic resistance might be due to an unknown mechanism. Correlating both is what makes the system powerful.

#### 2.5 Isolate Validator (Python)

**Why we use it**: Lab data is messy. Organism names are misspelled. MIC values are entered as text ("<=0.5" or ">32" or "R" instead of a number). Antibiotic names use non-standard abbreviations. Without validation, garbage data flows into analytics and produces garbage results.

**What it validates**:

- **Organism names**: Fuzzy-matched against NCBI Taxonomy database. "E. coli" → *Escherichia coli* (taxid 562). "Staph aureus" → *Staphylococcus aureus* (taxid 1280). Unresolvable names are flagged for manual review.
- **Antibiotic names**: Matched against the WHO ATC classification and WHONET antibiotic code list. Synonyms are resolved (e.g., "Cipro" → "Ciprofloxacin" → ATC J01MA02).
- **MIC values**: Parsed from text to structured format. "<=0.5" becomes `{value: 0.5, comparator: "<="}`. ">32" becomes `{value: 32, comparator: ">"}`. Values outside plausible ranges (e.g., MIC of 0.0001 or 999999) are flagged.
- **Disk diffusion zones**: Must be between 6mm (disk diameter) and ~50mm. Values outside this range indicate data entry errors.
- **Dates**: Validated and normalized to ISO 8601. Future dates are rejected. Dates more than 2 years old are flagged as potentially stale.
- **Deduplication**: Checks for duplicate specimens (same patient, same organism, same date) to prevent double-counting in surveillance analytics.

#### 2.6 De-identification Module (Python)

**Why we use it**: Patient privacy. AMR surveillance data should never contain patient-identifiable information beyond what's needed for epidemiological analysis. This module strips names, medical record numbers, and other direct identifiers. It retains age group (not exact date of birth), sex, and ward — enough for epidemiological stratification but not enough to identify individuals.

**How it works**: Runs as a mandatory pipeline step between validation and Kafka publication. Uses k-anonymity principles — if a combination of quasi-identifiers (age group + sex + ward + date) would identify fewer than k=5 individuals, the record is generalized further (e.g., age group broadened from "25-34" to "18-44").

#### 2.7 Apache Kafka (Event Bus)

**Why we use it**: Kafka is the industry standard for event streaming. It provides durable, ordered, partitioned event logs that multiple consumers can read independently. This is the architectural backbone that makes everything else possible.

**How we use it — topic design**:

| Topic | Partitioning Key | Content |
|---|---|---|
| `isolates.raw` | facility_id | Raw parsed isolate events before validation |
| `isolates.validated` | facility_id + organism | Validated, de-identified isolate events — the primary topic consumed by all downstream services |
| `isolates.genomic` | facility_id + specimen_id | WGS-derived genotypic resistance findings |
| `isolates.classified` | facility_id + organism | Events enriched with SIR classification from the breakpoint engine |
| `alerts.cusum` | facility_id | CUSUM/BOCPD outbreak alerts |
| `alerts.cluster` | facility_id | Spatiotemporal cluster alerts |
| `predictions.resistance` | organism + antibiotic | ML resistance predictions |
| `stewardship.recommendations` | facility_id | Agentic stewardship recommendations (for audit logging) |
| `dlq.validation_failures` | facility_id | Dead letter queue for events that failed validation |

**Partitioning strategy**: Partitioning by `facility_id` ensures that all events from the same facility are processed in order within the same partition. This is critical for CUSUM, which maintains per-facility state. Adding `organism` to the key for `isolates.validated` enables parallel processing across organism types.

**Retention policy**: 30 days for raw/validated topics (operational window). Indefinite for classified events (needed for historical trend analysis). 90 days for alerts. All events are also sunk to TimescaleDB for long-term storage.

**Consumer groups**: Each downstream service (breakpoint engine, CUSUM, ML predictor, GLASS exporter) runs as an independent Kafka consumer group. This means:
- Each service gets every event (fan-out pattern)
- Each service can scale independently by adding consumer instances within its group
- If one service goes down, the others are unaffected — Kafka retains events until the downed service recovers and catches up

#### 2.8 Apache Avro + Schema Registry

**Why we use it**: Without schema enforcement, a change in one parser's output format silently breaks every downstream consumer. Avro schemas define the exact structure of every event, and the Schema Registry enforces backward compatibility — you can add new optional fields but can't remove or rename existing ones without a conscious migration.

**How we use it**: Every Kafka topic has a registered Avro schema. Producers serialize events using the schema, embedding only the schema ID (not the full schema) in each message. Consumers look up the schema by ID from the registry and deserialize. If a producer tries to publish an event that doesn't conform to the registered schema, the serialization fails at the producer — bad data never enters Kafka.

**Schema evolution example**: When we add support for a new field (e.g., `patient_weight_kg` for dosing calculations), we add it as an optional field with a default value of null. Existing consumers that don't know about this field ignore it. New consumers can use it. No downtime, no coordinated deployment.

```json
{
  "type": "record",
  "name": "ValidatedIsolateEvent",
  "namespace": "org.amrsentinel.schema",
  "fields": [
    {"name": "event_id", "type": "string"},
    {"name": "facility_id", "type": "string"},
    {"name": "specimen_id", "type": "string"},
    {"name": "specimen_type", "type": "string"},
    {"name": "organism_ncbi_taxid", "type": "int"},
    {"name": "organism_name", "type": "string"},
    {"name": "antibiotic_atc_code", "type": "string"},
    {"name": "antibiotic_name", "type": "string"},
    {"name": "measurement_type", "type": {"type": "enum", "name": "MeasurementType", "symbols": ["MIC", "DISK"]}},
    {"name": "measurement_value", "type": "float"},
    {"name": "measurement_comparator", "type": ["null", "string"], "default": null},
    {"name": "patient_age_group", "type": ["null", "string"], "default": null},
    {"name": "patient_sex", "type": ["null", "string"], "default": null},
    {"name": "ward", "type": ["null", "string"], "default": null},
    {"name": "infection_origin", "type": ["null", {"type": "enum", "name": "InfectionOrigin", "symbols": ["COMMUNITY", "HOSPITAL", "UNKNOWN"]}], "default": null},
    {"name": "collection_date", "type": "string"},
    {"name": "ingested_at", "type": "string"},
    {"name": "breakpoint_version", "type": ["null", "string"], "default": null}
  ]
}
```

#### 2.9 TimescaleDB (Primary Data Store)

**Why we use it**: AST data is fundamentally time-series data — "organism X showed resistance Y at facility Z on date D." TimescaleDB is a PostgreSQL extension that adds automatic time-based partitioning (hypertables), continuous aggregates (incrementally updated materialized views), and columnar compression (90%+ storage reduction on older data). Since it's a PostgreSQL extension, you get full SQL compatibility, JPA/Hibernate support from your Spring Boot API gateway, and no operational overhead of learning a new database.

**How we use it — core tables**:

```sql
-- Main isolate event table (hypertable, partitioned by collection_date)
CREATE TABLE isolate_events (
    event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id     VARCHAR(50) NOT NULL,
    specimen_id     VARCHAR(100) NOT NULL,
    specimen_type   VARCHAR(20),
    organism_taxid  INT NOT NULL,
    organism_name   VARCHAR(255) NOT NULL,
    antibiotic_atc  VARCHAR(10) NOT NULL,
    antibiotic_name VARCHAR(100) NOT NULL,
    measurement_type VARCHAR(4) NOT NULL,  -- MIC or DISK
    measurement_value FLOAT NOT NULL,
    measurement_comparator VARCHAR(2),      -- <=, >=, =, >
    sir_classification CHAR(1),             -- S, I, R (filled by breakpoint engine)
    breakpoint_standard VARCHAR(10),        -- EUCAST or CLSI
    breakpoint_version VARCHAR(10),         -- e.g., "2025.1"
    patient_age_group VARCHAR(10),
    patient_sex CHAR(1),
    ward VARCHAR(50),
    infection_origin VARCHAR(20),
    collection_date TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    classified_at TIMESTAMPTZ
);

-- Convert to hypertable (automatic time-based partitioning)
SELECT create_hypertable('isolate_events', 'collection_date',
    chunk_time_interval => INTERVAL '1 month');

-- Continuous aggregate: daily resistance rates per facility/organism/antibiotic
CREATE MATERIALIZED VIEW daily_resistance_rates
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', collection_date) AS day,
    facility_id,
    organism_name,
    antibiotic_name,
    COUNT(*) FILTER (WHERE sir_classification = 'R') AS resistant_count,
    COUNT(*) AS total_count,
    COUNT(*) FILTER (WHERE sir_classification = 'R')::float / NULLIF(COUNT(*), 0) AS resistance_rate
FROM isolate_events
WHERE sir_classification IS NOT NULL
GROUP BY day, facility_id, organism_name, antibiotic_name;

-- Compression policy: compress chunks older than 6 months
SELECT add_compression_policy('isolate_events', INTERVAL '6 months');

-- Retention policy: drop raw data older than 5 years (aggregates retained)
SELECT add_retention_policy('isolate_events', INTERVAL '5 years');
```

**Why continuous aggregates matter**: When a clinician asks "what's the ciprofloxacin resistance rate for E. coli at my hospital this quarter?", a naive query would scan every isolate event for that period. With millions of events, this takes seconds. A continuous aggregate pre-computes daily rates in the background as new data arrives, so the same query hits a small materialized view and returns in milliseconds. This is what powers the real-time dashboard.

---

## 3. Layer 2 — Intelligence Engine

### Purpose

Process every validated isolate event through three analytical tiers: classification (what does this result mean?), surveillance (is something abnormal happening?), and prediction (what's likely to happen next?). This layer transforms raw lab data into actionable intelligence.

### Tier 2a — Classification (Stream Processing, Sub-Second Latency)

These modules run as Apache Flink stream processors, consuming directly from Kafka. Every isolate event is classified within milliseconds of arrival.

#### 3.1 Apache Flink (Stream Processing Engine)

**Why we use it**: Flink is the standard for stateful stream processing. Unlike simple Kafka consumers that process one event at a time, Flink can maintain state (like running CUSUM sums) across events, handle event-time semantics (process events based on when they occurred, not when they arrived), and guarantee exactly-once processing even during failures.

**How we use it**: Flink runs as a cluster (JobManager + TaskManagers) deployed on Kubernetes. Each analytical module is a Flink job that:
1. Reads from a Kafka topic (e.g., `isolates.validated`)
2. Processes each event through its logic (e.g., breakpoint classification)
3. Updates internal state if needed (e.g., CUSUM running sum)
4. Writes results to another Kafka topic (e.g., `isolates.classified`) and/or directly to TimescaleDB via a Flink JDBC sink

**Why Flink over Kafka Streams**: Kafka Streams is lighter-weight and runs embedded in your application (no separate cluster). But Flink provides: event-time windowing (essential for handling out-of-order lab results), savepoints (snapshot and restore state for upgrades), and native Python support (PyFlink) which matters because all our intelligence modules are Python. Flink also scales better for high-throughput scenarios — when this system is deployed nationally across hundreds of facilities, Flink handles the parallelism natively.

#### 3.2 Breakpoint Engine (Flink Job — Python/PyFlink)

**Why we use it**: Raw lab measurements (MIC values, disk zone diameters) are meaningless to clinicians. They need SIR classifications — Susceptible, Intermediate, or Resistant. The breakpoint engine converts raw measurements to SIR using standardized rules.

**What are breakpoints**: Breakpoints are threshold values published by EUCAST (European) and CLSI (American) that define the boundary between susceptible and resistant for each organism-antibiotic-measurement method combination. For example:

- *E. coli* + Ciprofloxacin + MIC: S ≤ 0.25 µg/mL, R > 0.5 µg/mL (EUCAST 2025)
- *E. coli* + Ciprofloxacin + Disk (5µg): S ≥ 25 mm, R < 22 mm (EUCAST 2025)

Note that the breakpoint values are different for MIC (lower = more susceptible) and disk diffusion (higher = more susceptible), because they measure opposite things — MIC is the minimum concentration needed to kill the bacteria (lower = easier to kill), while disk diffusion measures how far the antibiotic diffuses and inhibits growth (larger zone = more susceptible).

**How we implement it**:

1. **Breakpoint table source**: We load the complete EUCAST and CLSI breakpoint tables from the AMR R package (amr-for-r.org), which maintains a curated dataset of 40,217+ breakpoint records across all clinically relevant organism-antibiotic combinations. This dataset is published under GPLv2 with explicit EUCAST and CLSI endorsement.

2. **Loading into the engine**: At startup, the breakpoint engine loads the full breakpoint table into an in-memory lookup structure (Python dictionary keyed by organism_taxid + antibiotic_atc + measurement_type + standard). This lookup is O(1) per classification.

3. **Classification logic** (for each isolate event):
   ```
   Input: organism_taxid=562, antibiotic_atc="J01MA02", 
          measurement_type=MIC, value=4.0, standard=EUCAST
   
   Lookup: breakpoints[562]["J01MA02"]["MIC"]["EUCAST"]
   → S_threshold=0.25, R_threshold=0.5
   
   Compare: 4.0 > 0.5 → classification = "R"
   
   Output: original event + {sir="R", breakpoint_standard="EUCAST", 
           breakpoint_version="2025.1"}
   ```

4. **Version pinning**: Critical detail — the engine stores which breakpoint version was used for each classification. EUCAST and CLSI update breakpoints annually. If the threshold for ciprofloxacin changes from R > 0.5 to R > 0.25 next year, historical resistance rates will appear to jump — not because resistance actually increased, but because the definition changed. Version pinning lets you detect and adjust for this.

5. **Intrinsic resistance handling**: Some organisms are inherently resistant to certain antibiotics (e.g., *Klebsiella pneumoniae* is intrinsically resistant to ampicillin). The breakpoint engine flags these as "intrinsically resistant" rather than classifying from the measurement, because the MIC value is irrelevant — the organism will always be resistant regardless of the number.

6. **Expert rules**: Beyond simple threshold comparison, some breakpoints have expert rules. For example, EUCAST specifies that if *Staphylococcus aureus* is resistant to oxacillin (MRSA), it should be reported as resistant to ALL beta-lactams regardless of their individual MIC values. These rules are implemented as a post-classification step.

**Output**: The classified event is published to `isolates.classified` and written to TimescaleDB (updating the `sir_classification`, `breakpoint_standard`, and `breakpoint_version` columns).

#### 3.3 WHO AWaRe Classifier (Flink Job)

**Why we use it**: The WHO AWaRe (Access, Watch, Reserve) classification categorizes antibiotics by their importance for stewardship:
- **Access**: First-line antibiotics for common infections. Should be widely available. Examples: amoxicillin, metronidazole.
- **Watch**: Antibiotics with higher resistance potential. Should be prioritized as key targets for stewardship. Examples: ciprofloxacin, azithromycin, ceftriaxone.
- **Reserve**: Last-resort antibiotics for multi-drug-resistant infections. Should be used only when all other alternatives have failed. Examples: colistin, linezolid, daptomycin.

**How we use it**: Every antibiotic in the system is tagged with its AWaRe category at classification time. This feeds into the agentic stewardship layer — when the agent recommends an antibiotic, it includes the AWaRe category and explains why a Watch or Reserve antibiotic is being suggested instead of an Access one.

**Implementation**: A simple lookup table from ATC code to AWaRe category, sourced from the WHO AWaRe 2023 classification (the most recent as of 2026). The lookup runs in the same Flink job as the breakpoint engine (it's a simple enrichment step, not a separate job).

#### 3.4 CLSI M39 Antibiogram Generator (Batch — Python/Celery)

**Why we use it**: An antibiogram is the single most important reference document for empiric therapy decisions. It shows the percentage of each organism that's susceptible to each antibiotic at a specific facility over a specific time period. Clinicians use it to answer: "Before I get this patient's lab results back, which antibiotic is most likely to work?"

**Why batch, not stream**: Antibiograms are computed over a period (typically quarterly or annually) and must follow specific statistical rules. They don't need sub-second latency — they're generated on a schedule (e.g., quarterly) or on-demand.

**How we implement it — CLSI M39 rules**:

CLSI M39 is the standard for antibiogram construction. The key rules are:

1. **First isolate rule**: Only the first isolate of each organism per patient per analysis period is included. If a patient's blood culture grows *E. coli* three times in a quarter, only the first occurrence counts. This prevents a single severely infected patient from skewing the facility's resistance rates. Implementation: `SELECT DISTINCT ON (patient_id, organism_taxid) ... ORDER BY collection_date ASC`.

2. **Minimum sample size**: At least 30 isolates of an organism are required to report a susceptibility rate. Below 30, the confidence interval is too wide to be useful. Organism-antibiotic combinations with <30 isolates are omitted from the antibiogram with a note "insufficient data."

3. **Percent susceptible (%S)**: The primary metric is the percentage of isolates classified as S (susceptible). Not %R (resistant), because %S is what the clinician needs — "what's the probability this antibiotic will work?" %S of 85% means 85 out of 100 patients with this organism would respond to this antibiotic.

4. **Stratification**: Antibiograms can be stratified by ward (ICU vs. non-ICU), specimen type (blood vs. urine), and infection origin (community vs. hospital-acquired). ICU antibiograms often show significantly higher resistance than hospital-wide ones.

**Output**: The generator produces:
- A structured JSON antibiogram object (consumed by the agentic layer's `query_antibiogram` tool)
- A PDF report (generated via ReportLab) formatted as the standard antibiogram table that clinicians are familiar with — organisms as rows, antibiotics as columns, %S values in cells, color-coded (green ≥ 80%, yellow 60-79%, red < 60%)

### Tier 2b — Surveillance (Stream Processing, Seconds to Minutes)

#### 3.5 Hybrid Outbreak Detection: Binary CUSUM + BOCPD (Flink Job — Python/PyFlink)

This is the most technically sophisticated component of the system and the single biggest differentiator from existing tools.

**The problem**: How do you detect, in near-real-time, that the resistance rate for a given organism-antibiotic combination at a given facility has shifted above its historical baseline? This is outbreak detection — catching a problem before it becomes a crisis.

**Why two methods**: No single statistical method is optimal for all types of resistance shifts. We use two complementary approaches in an ensemble.

##### Binary CUSUM (Cumulative Sum)

**What it is**: A sequential statistical test originally developed by E.S. Page in 1954 for manufacturing quality control. Adapted for hospital infection surveillance by the CDC in the early 2000s.

**How it works mathematically**:

Consider a stream of binary events: each new AST result for a specific organism-antibiotic at a specific facility is either R (resistant, coded as 1) or S/I (susceptible/intermediate, coded as 0).

Define:
- p₀ = baseline resistance rate (historical average, e.g., 0.20 = 20% resistant)
- p₁ = the elevated rate you want to detect (e.g., 0.35 = 35% resistant)
- k = reference value = ln((p₁(1-p₀)) / (p₀(1-p₁))) / ln((p₁(1-p₀)) / (p₀(1-p₁))) — simplified, it's typically set to (p₀ + p₁) / 2
- h = decision threshold (controls the tradeoff between sensitivity and false positive rate)

For each new observation xₙ (0 or 1):
```
Sₙ = max(0, Sₙ₋₁ + (xₙ - k))
```

If Sₙ ≥ h, trigger an alert. Reset Sₙ to 0 after an alert (or not, depending on the scheme).

**Intuition**: The running sum Sₙ accumulates evidence. When the actual resistance rate is at baseline (p₀), the expected increment per observation is (p₀ - k) < 0, so the sum drifts downward and gets reset to 0 by the max(0, ...) term. When the actual rate shifts to p₁ or higher, the expected increment becomes positive, the sum drifts upward, and eventually crosses the threshold.

**Parameter selection**: We use the approach from the 2002 CDC study on CUSUM for hospital infection surveillance:
- p₀ is computed from the facility's own historical data (rolling 12-month baseline)
- p₁ is set to 1.5 × p₀ (detect a 50% relative increase)
- h is calibrated to achieve a target Average Run Length (ARL) of 50 under the null hypothesis — meaning, on average, you'd get one false alarm per 50 observations when resistance hasn't actually increased

**Implementation in Flink**: Flink's keyed state stores the CUSUM running sum (Sₙ) and baseline rate (p₀) for each unique key (facility_id, organism_taxid, antibiotic_atc). When a new classified event arrives:
1. Look up the state for this key
2. Compute the new sum
3. If sum ≥ h, emit an alert to `alerts.cusum` and reset
4. Update the state

**Strengths of CUSUM**: Fast, computationally trivial (O(1) per event), well-understood statistical properties, decades of validation in hospital settings.

**Weaknesses of CUSUM**: Requires pre-specified parameters (p₁ and h). If a novel resistance mechanism causes a shift of a different magnitude than what you tuned for (e.g., a small gradual drift rather than a sudden jump), CUSUM may detect it very slowly or not at all. It also assumes the baseline rate is stable, which isn't always true.

##### Bayesian Online Changepoint Detection (BOCPD)

**What it is**: An algorithm developed by Adams & MacKay (2007) that detects changes in the statistical properties of a data stream without requiring pre-specified shift parameters. It maintains a probability distribution over "run lengths" — how long since the last changepoint.

**How it works conceptually**:

At each time step, BOCPD answers the question: "Given everything I've seen so far, what's the probability that the most recent changepoint was 0, 1, 2, ... , t time steps ago?"

The algorithm maintains a vector of run-length probabilities. A "run length" of 0 means "a changepoint just happened" (the current observation starts a new regime). A run length of 10 means "the last 10 observations came from the same underlying distribution."

For each new observation:
1. **Growth probabilities**: For each possible run length r, compute how likely the new observation is under the model that has been running for r steps (using sufficient statistics accumulated over those r steps)
2. **Changepoint probability**: Compute the probability that a changepoint just occurred (using the hazard function — typically assumed constant, meaning changepoints are equally likely at any time)
3. **Update**: Combine growth and changepoint probabilities to get the new run-length distribution
4. **Detection**: If the probability mass at run length 0 exceeds a threshold, a changepoint has been detected — the resistance rate has shifted

**Why it's complementary to CUSUM**: BOCPD doesn't need you to specify p₁ (the elevated rate to detect). It detects *any* statistically significant change in the underlying resistance rate, regardless of direction or magnitude. This catches:
- Novel resistance mechanisms that cause unexpected patterns
- Gradual MIC drift (resistance creeping upward slowly over months)
- Sudden drops in resistance (which might indicate a successful stewardship intervention)

**Implementation**: We use a Beta-Bernoulli conjugate model (since our data is binary — resistant/susceptible). The run-length distribution is truncated at a maximum of 500 steps to bound memory usage. The hazard rate (probability of a changepoint at any step) is set to 1/250, meaning we expect a regime to last about 250 observations on average.

**Ensemble logic**:

| CUSUM | BOCPD | Alert Level | Interpretation |
|---|---|---|---|
| Fired | Fired | HIGH | Strong evidence — both methods agree that resistance has increased above baseline |
| Fired | Silent | MODERATE | Expected shift detected — the increase matches the magnitude CUSUM was tuned for |
| Silent | Fired | INVESTIGATE | Unexpected change detected — could be a novel pattern, gradual drift, or transient fluctuation. Warrants investigation |
| Silent | Silent | None | No evidence of a shift |

HIGH alerts are pushed immediately to infection control teams via webhook. MODERATE alerts appear on the dashboard. INVESTIGATE alerts are logged and reviewed in weekly surveillance reports.

#### 3.6 Spatiotemporal Clustering (Flink Job)

**Why we use it**: AMR doesn't just rise in aggregate — it spreads through specific pathways. Three MRSA infections in the same ICU within a week is a potential transmission event that demands immediate infection control response (contact tracing, environmental cleaning, cohorting). A generic "MRSA resistance rate increased" alert doesn't capture this urgency.

**How it works**: The module correlates resistance events across two dimensions:

1. **Spatial**: Ward-level location data. Events from the same ward or adjacent wards within a short time window are flagged as a potential cluster. We use a simple sliding window approach: if N or more resistant isolates of the same organism appear in the same ward within D days (configurable, typically N=3, D=7), a cluster alert is generated.

2. **One Health signals**: If the same resistance gene (from WGS data) appears in clinical isolates AND food chain samples (from NARMS data or similar) from the same geographic region within a time window, it suggests environmental transmission. This is the One Health dimension that no current surveillance tool captures.

**Output**: Cluster alerts include the ward(s) involved, the organism, the timeline, and (if WGS data is available) whether the isolates share the same sequence type, suggesting clonal transmission.

### Tier 2c — Prediction and Knowledge (Batch, Minutes to Hours)

#### 3.7 ML Resistance Predictor: XGBoost + Temporal Transformer Ensemble (Python/Celery)

**Why we use it**: Beyond detecting current resistance, clinicians need predictions. "If a patient presents tomorrow with a UTI caused by *E. coli* at my hospital, what's the probability of ciprofloxacin resistance?" This informs empiric therapy before any lab results are available.

**Why an ensemble of two models**:

**XGBoost**: Excels at tabular feature interactions. It captures cross-feature patterns like "hospital-acquired + ICU + South Asia → high carbapenem resistance." Trained on the Pfizer ATLAS dataset (917,000+ isolates, 2004-2021, 89 countries). Features include:
- Geographic region (WHO region + country)
- Specimen type (blood, urine, respiratory, wound)
- Infection origin (community vs. hospital)
- Patient age group
- Year (captures long-term resistance trends)
- Facility-level historical resistance rate (from continuous aggregates)
- Organism (encoded as taxid)
- Antibiotic class (beta-lactam, fluoroquinolone, etc.)

**Temporal Transformer**: Captures sequential patterns that XGBoost misses. Specifically, it models the *trajectory* of resistance rates over time — "this organism's MIC has been creeping upward for 6 months, even though it hasn't crossed the resistance breakpoint yet." This is sub-breakpoint drift, and it's the earliest signal that full resistance is coming. The transformer takes as input a time series of monthly resistance rates for a specific organism-antibiotic-facility combination and predicts the next month's rate.

**Ensemble combination**: Both models output a probability. The ensemble uses a learned weighting (a simple logistic regression trained on a held-out validation set) that combines them:
```
P_ensemble = σ(w₁ · logit(P_xgb) + w₂ · logit(P_transformer) + b)
```

**Explainability via SHAP**: Both models produce SHAP (SHapley Additive exPlanations) values. These tell you *why* the model predicts high resistance — "hospital-acquired infection contributed +15%, ICU ward contributed +8%, recent facility resistance trend contributed +12%." This is critical for clinician trust — a black-box prediction is useless in clinical practice.

**Training pipeline**: Runs as a scheduled Celery task (monthly retraining). Downloads latest data from ATLAS (if available) and supplements with the facility's own data from TimescaleDB. XGBoost is retrained via standard scikit-learn/XGBoost pipeline. Temporal transformer is retrained using PyTorch with the facility's time-series data. Model artifacts are versioned and stored in S3.

**Claude-as-judge eval harness**: Same pattern from Artha. A panel of evaluation queries (e.g., "For a 70-year-old ICU patient with hospital-acquired pneumonia, should I use piperacillin-tazobactam or meropenem?") are run through the system. Claude evaluates the recommendation on four dimensions: clinical appropriateness, alignment with guidelines, use of local data, and explanation quality. This is a quality gate — a new model version isn't deployed unless it passes the eval harness.

#### 3.8 AMR Knowledge Graph (Neo4j)

**Why we use it**: The knowledge graph is what makes AMR Sentinel an intelligence platform rather than just an analytics dashboard. It encodes the relationships between organisms, antibiotics, resistance genes, resistance mechanisms, and clinical guidelines in a queryable graph structure.

**Why Neo4j**: Graph databases represent relationships as first-class citizens. "Which resistance genes does *Klebsiella pneumoniae* commonly carry, and which antibiotics do they affect?" is a natural graph query (2-3 Cypher hops). In a relational database, this is a complex multi-table join. Neo4j also has a mature Python driver, a built-in visualization tool (Neo4j Bloom), and the Graph Data Science library for running graph algorithms.

**Schema design — nodes**:

| Node Label | Key Properties | Source |
|---|---|---|
| `Organism` | ncbi_taxid, name, gram_stain, family, genus, species | NCBI Taxonomy |
| `Antibiotic` | atc_code, name, drug_class, aware_category, route | WHO ATC + AWaRe |
| `ResistanceGene` | gene_name, gene_family, accession | CARD (Comprehensive Antibiotic Resistance Database) |
| `ResistanceMechanism` | name: "Enzymatic inactivation", "Efflux pump", "Target modification", "Porin loss", "Target protection" | CARD |
| `DrugClass` | name: "Fluoroquinolones", "Carbapenems", "Cephalosporins", etc. | ATC hierarchy |
| `Guideline` | source (WHO/IDSA/local), condition, recommendation | Manual curation |
| `Facility` | facility_id, name, country, facility_type | Registration data |
| `Ward` | ward_id, name, type (ICU/general/surgical/pediatric) | Registration data |

**Schema design — relationships**:

```cypher
// Organism carries a resistance gene
(Organism)-[:CARRIES {prevalence: 0.45, evidence: "WGS"}]->(ResistanceGene)

// Resistance gene confers a mechanism
(ResistanceGene)-[:CONFERS]->(ResistanceMechanism)

// Mechanism acts against a drug class
(ResistanceMechanism)-[:ACTS_AGAINST]->(DrugClass)

// Drug class contains specific antibiotics
(DrugClass)-[:CONTAINS]->(Antibiotic)

// Organism shows phenotypic resistance to antibiotic (from surveillance data)
(Organism)-[:PHENOTYPIC_RESISTANCE {rate: 0.32, facility: "HOSP_001", period: "2026-Q1"}]->(Antibiotic)

// Guideline recommends antibiotic for condition caused by organism
(Guideline)-[:RECOMMENDS {strength: "strong", condition: "uncomplicated UTI"}]->(Antibiotic)
(Guideline)-[:FOR_ORGANISM]->(Organism)

// Co-occurrence: genes that frequently appear together
(ResistanceGene)-[:CO_OCCURS_WITH {frequency: 0.78}]->(ResistanceGene)
```

**Why this matters for stewardship**: When the agentic layer gets a query like "what should I prescribe for a suspected *Klebsiella* bloodstream infection?", it doesn't just look up the antibiogram. It traverses the knowledge graph:

1. Check which resistance genes *Klebsiella pneumoniae* commonly carries at this facility (from WGS data correlated with phenotypic data)
2. If bla-KPC is prevalent (carbapenemase), know that carbapenems are likely ineffective
3. Check co-occurrence: bla-KPC frequently co-occurs with aac(6')-Ib (aminoglycoside resistance), so aminoglycosides may also be compromised
4. Traverse to find which drug classes are NOT affected by the prevalent resistance mechanisms
5. Cross-reference with guidelines and the facility antibiogram
6. Recommend an antibiotic that bypasses the known resistance mechanisms, with an explanation of the reasoning

This is the kind of reasoning that no existing AMR tool can do. It requires connecting phenotypic surveillance data, genotypic data, mechanism knowledge, and clinical guidelines in a single queryable structure.

**Data sources for populating the graph**:
- **CARD** (Comprehensive Antibiotic Resistance Database): 5,000+ resistance genes, their mechanisms, and the antibiotics they affect. Available via their API and OWL ontology.
- **NCBI Taxonomy**: Complete bacterial taxonomy for organism nodes.
- **WHO ATC**: Antibiotic classification hierarchy.
- **ResFinder database**: Acquired resistance gene sequences.
- **Facility surveillance data**: Phenotypic resistance rates from the system's own data, updated via a nightly Celery job.

#### 3.9 GLASS Export Generator (Batch — Python/Celery)

**Why we use it**: WHO's Global Antimicrobial Resistance and Use Surveillance System (GLASS) requires countries to submit AMR data in a very specific format. Currently, this is a manual, error-prone process that many countries can't do. Automating it removes a major barrier to global surveillance participation.

**How it works**: The generator reads classified isolate data from TimescaleDB, applies GLASS data quality rules (deduplication, first isolate per patient, minimum sample sizes), and produces three output files:

1. **RIS file** (Resistance data): One row per organism-antibiotic combination per facility, with counts of S, I, R, and total tested.
2. **SAMPLE file** (Specimen metadata): Demographic breakdowns of specimens (age groups, sex, specimen types).
3. **Quality indicators**: GLASS-defined metrics like "percentage of blood cultures with valid AST" and "percentage of isolates with species-level identification."

The output conforms to the GLASS 2025 format specification. Validation checks run against the published GLASS format schema before export, achieving 100% format compliance on shadow testing.

---

## 4. Layer 3 — Agentic Stewardship Layer

### Purpose

Synthesize structured outputs from Layer 2 into natural language clinical decision support using Claude API tool-calling. This is the same architectural pattern as Artha's agentic layer — an LLM orchestrates a set of typed tools, each returning structured data from the intelligence engine.

### Architecture

**Technology**: Anthropic Claude API with tool-calling (the `tool_use` feature). The agentic service is a Python/FastAPI application that:
1. Receives a natural language query from a clinician (via the dashboard or API)
2. Constructs a system prompt with the available tools and safety constraints
3. Sends the query to Claude with the tool definitions
4. Claude selects which tools to call and with what parameters
5. The service executes the tool calls against Layer 2 services
6. Tool results are sent back to Claude
7. Claude synthesizes a response grounded in the tool results

This is the same perception → reasoning → action → response loop from Artha, applied to a different domain.

### Tool Definitions

#### 4.1 `recommend_empiric_therapy`

**Purpose**: The flagship tool. Given clinical context, recommend ranked antibiotic options for empiric therapy.

**Input parameters**:
- `organism` (optional): If the pathogen is known or suspected
- `infection_site`: e.g., "urinary tract", "bloodstream", "respiratory", "skin/soft tissue"
- `patient_context`: Age group, ward, infection origin (community/hospital)
- `facility_id`: Which facility's data to use

**What it does internally**:
1. Queries the antibiogram for the relevant organism at the given facility
2. Gets ML resistance predictions for each candidate antibiotic
3. Checks AWaRe classification for each candidate
4. Traverses the knowledge graph for resistance mechanism context
5. Cross-references with applicable guidelines (WHO, IDSA)
6. Ranks antibiotics by predicted efficacy × AWaRe preference (favoring Access over Watch over Reserve)

**Output**: A ranked list of antibiotic recommendations, each with: predicted %S, AWaRe category, SHAP-based justification, guideline concordance, and any relevant knowledge graph context (e.g., "bla-CTX-M-15 prevalence at this facility is 34%, which affects all third-generation cephalosporins").

#### 4.2 `predict_resistance`

**Purpose**: Return the ML ensemble prediction for a specific organism-antibiotic combination.

**Input**: organism, antibiotic, patient_context, facility_id

**Output**: Predicted resistance probability (0-1), confidence interval, SHAP feature importance breakdown, model version, training data size.

#### 4.3 `get_outbreak_alerts`

**Purpose**: Retrieve active CUSUM/BOCPD alerts for a facility.

**Input**: facility_id, severity_filter (HIGH/MODERATE/INVESTIGATE), time_range

**Output**: List of active alerts with: organism, antibiotic, alert type (CUSUM/BOCPD/both), severity, date triggered, current resistance rate vs. baseline, and spatiotemporal cluster context if applicable.

#### 4.4 `query_antibiogram`

**Purpose**: Return the current antibiogram for a facility.

**Input**: facility_id, organism (optional), time_period, stratification (ward/specimen_type/infection_origin)

**Output**: Structured antibiogram table with %S values, sample sizes, and trend indicators (↑/↓/→ compared to previous period).

#### 4.5 `check_guideline_grounding`

**Purpose**: Validate a proposed antibiotic choice against published guidelines.

**Input**: antibiotic, organism, infection_site, guideline_source (WHO/IDSA/local)

**Output**: Concordance (concordant/discordant/no guidance), the specific guideline recommendation, and the strength of evidence.

#### 4.6 `traverse_knowledge_graph`

**Purpose**: Answer complex mechanistic questions by traversing the Neo4j knowledge graph.

**Input**: A structured query, e.g., `{start_node: "Klebsiella pneumoniae", relationship: "CARRIES", depth: 3}`

**Output**: Graph traversal results — which genes the organism carries, which mechanisms they confer, which drug classes are affected.

#### 4.7 `advise_de_escalation`

**Purpose**: Given a patient's current broad-spectrum therapy and their lab results (now available), recommend narrower-spectrum alternatives.

**Input**: current_antibiotic, organism, sir_results (full panel), patient_context

**Output**: De-escalation options ranked by: spectrum narrowness, AWaRe category (prefer Access), predicted efficacy based on the actual SIR results.

### Safety Layer

Every agentic response includes:
- **Mandatory disclaimer**: "This is decision support, not a prescription. Clinical judgment must always override AI recommendations."
- **Confidence score**: Based on data quality and quantity — if the antibiogram has <30 isolates, confidence is flagged as LOW
- **Data provenance**: "Based on 847 E. coli isolates from your facility, January-March 2026, classified using EUCAST 2025 breakpoints"
- **AWaRe flag**: Prominent warning when Watch or Reserve antibiotics are recommended
- **Audit logging**: Every tool call and recommendation is logged to TimescaleDB and the `stewardship.recommendations` Kafka topic for compliance review

---

## 5. Layer 4 — Reporting, Dashboards & Integration

### 5.1 Real-Time Dashboard (React + D3/Recharts)

**Purpose**: Visual command center for infection control teams and stewardship pharmacists.

**Key views**:
- **Resistance trend heatmap**: Organisms as rows, antibiotics as columns, %S as cell color. Filterable by time period, ward, specimen type.
- **CUSUM/BOCPD status board**: Traffic light indicators for every monitored organism-antibiotic combination. Green = normal, yellow = MODERATE alert, red = HIGH alert.
- **AWaRe distribution chart**: Pie/bar chart showing the facility's antibiotic consumption by AWaRe category over time. Target: ≥60% Access (WHO goal).
- **Spatiotemporal cluster map**: Floor plan or ward layout showing active transmission clusters.
- **Stewardship scorecard**: Metrics like "% prescriptions concordant with guidelines," "% de-escalation within 72 hours," "Watch/Reserve antibiotic usage trend."

**Technology**: React 18 frontend, D3.js for custom visualizations, Recharts for standard charts, WebSocket connection to the Spring Boot API gateway for real-time alert push.

### 5.2 GLASS Automated Reporting

One-click generation of GLASS-compliant export files. The dashboard provides a "Generate GLASS Report" button that triggers the GLASS export generator (section 3.9), validates the output, and provides a downloadable ZIP containing the RIS, SAMPLE, and quality indicator files.

### 5.3 REST + GraphQL API (Spring Boot)

**Why both**: REST for simple CRUD operations (get antibiogram, get alerts, get facility data). GraphQL for complex nested queries that leverage the knowledge graph ("give me all resistance mechanisms affecting carbapenems in *Acinetobacter baumannii* with their prevalence at my facility and the recommended alternatives from WHO guidelines").

**Spring Boot API Gateway**: This is the single entry point for all external requests. It handles authentication (JWT), authorization (role-based — clinician, pharmacist, infection control, admin), multi-tenancy (each facility sees only its own data), rate limiting, and request routing to the appropriate backend service.

### 5.4 Webhooks + FHIR Outbound

**Webhooks**: Configurable HTTP callbacks for outbreak alerts. Infection control teams can register webhook URLs that receive real-time POST requests when HIGH-severity alerts fire. Payload includes the alert details and a link to the dashboard.

**FHIR outbound**: For hospitals with FHIR-capable EHRs, the system can push DiagnosticReport resources back to the EHR with enriched SIR classifications, SHAP-explained predictions, and stewardship recommendations. This puts the intelligence directly in the clinician's workflow.

### 5.5 PDF Report Generation (ReportLab)

Automated generation of:
- Quarterly antibiogram PDFs (the standard format clinicians are used to)
- Outbreak investigation reports (timeline, affected patients/wards, recommended interventions)
- Monthly stewardship compliance reports
- GLASS submission summaries

### 5.6 Audit Log + Compliance Trail

Every data point, classification, prediction, and recommendation is logged with:
- Timestamp
- Data version (which isolates were in the dataset)
- Model version (which ML model was used)
- Breakpoint version (which EUCAST/CLSI rules were applied)
- User context (who requested the recommendation)

This is critical for clinical governance — if a recommendation is ever questioned, the full provenance chain can be reconstructed.

### 5.7 Mobile Push Alerts

For outbreak alerts, push notifications to registered mobile devices of infection control team members. Implemented via Firebase Cloud Messaging (FCM) or similar.

---

## 6. Infrastructure & Deployment

### Deployment Architecture

Everything runs on Kubernetes (your existing expertise), deployed on AWS (your existing stack).

| Component | Deployment | Scaling |
|---|---|---|
| WHONET/CSV/FHIR Parsers | K8s Deployment (3 replicas) | HPA based on request rate |
| Kafka | Amazon MSK (managed) or self-hosted on K8s | 3+ brokers, replication factor 3 |
| Schema Registry | K8s Deployment (2 replicas) | Stateless, scales easily |
| Flink Cluster | K8s (Flink Operator) | TaskManager scaling based on Kafka lag |
| TimescaleDB | Amazon RDS (PostgreSQL) with TimescaleDB extension, or self-hosted | Vertical scaling + read replicas |
| Neo4j | K8s StatefulSet or Neo4j Aura (managed) | Read replicas for query scaling |
| Celery Workers | K8s Deployment | HPA based on queue depth |
| Redis (Celery broker) | Amazon ElastiCache or K8s | Standard HA setup |
| Spring Boot API Gateway | K8s Deployment (3+ replicas) | HPA based on CPU/request rate |
| Agentic Service (FastAPI) | K8s Deployment (2+ replicas) | Scales with Claude API rate limits |
| React Dashboard | S3 + CloudFront (static hosting) | CDN handles scaling |

### Infrastructure as Code

All deployed via Terraform (your existing tool). Module structure:

```
terraform/
├── modules/
│   ├── vpc/              # VPC, subnets, security groups
│   ├── eks/              # EKS cluster configuration
│   ├── msk/              # Kafka (Amazon MSK)
│   ├── rds/              # TimescaleDB (RDS PostgreSQL)
│   ├── elasticache/      # Redis for Celery
│   ├── s3/               # ML model artifacts, GLASS exports, dashboard hosting
│   └── monitoring/       # CloudWatch, Prometheus, Grafana
├── environments/
│   ├── dev/
│   ├── staging/
│   └── production/
└── main.tf
```

### CI/CD

GitHub Actions with path-filtered workflows (same pattern you set up for the deals aggregator monorepo):

```
.github/workflows/
├── ingestion.yml         # Triggered by changes in services/ingestion/
├── intelligence.yml      # Triggered by changes in services/intelligence/
├── api-gateway.yml       # Triggered by changes in services/gateway/
├── agentic.yml           # Triggered by changes in services/agentic/
├── dashboard.yml         # Triggered by changes in frontend/
└── infrastructure.yml    # Triggered by changes in terraform/
```

### Monitoring & Observability

- **Prometheus + Grafana**: Metrics from all services — Kafka lag, Flink throughput, CUSUM alert rates, API latency, ML model inference time
- **ELK Stack or Loki**: Centralized logging from all services
- **OpenTelemetry**: Distributed tracing across the event pipeline (parser → Kafka → Flink → TimescaleDB)
- **PagerDuty/OpsGenie**: Alert routing for infrastructure issues

---

## 7. Data Flow — End to End

Here's the complete journey of a single AST result from lab bench to clinical recommendation:

1. **Lab technician** runs an antibiotic susceptibility test on a blood culture isolate. Result: *E. coli*, Ciprofloxacin, MIC = 4 µg/mL.

2. **Lab information system** exports the result as part of a WHONET batch file or FHIR DiagnosticReport.

3. **WHONET Parser** (Layer 1) reads the file, maps organism and antibiotic codes to standards, extracts the MIC value, and publishes a `ValidatedIsolateEvent` to `isolates.validated`.

4. **Breakpoint Engine** (Layer 2a, Flink) consumes the event within milliseconds. Looks up EUCAST 2025 breakpoints for E. coli + Ciprofloxacin + MIC: S ≤ 0.25, R > 0.5. Since 4.0 > 0.5, classifies as R. Publishes enriched event to `isolates.classified` and writes to TimescaleDB.

5. **AWaRe Classifier** (Layer 2a, same Flink job) tags Ciprofloxacin as "Watch" category.

6. **CUSUM** (Layer 2b, Flink) updates the running sum for (facility, E. coli, Ciprofloxacin). The sum has been climbing — this is the 5th resistant E. coli ciprofloxacin isolate in two weeks. Sum crosses threshold h. Emits a MODERATE alert to `alerts.cusum`.

7. **BOCPD** (Layer 2b, same Flink job) updates the run-length distribution. The posterior probability at run length 0 (changepoint just happened) is 0.82, well above the 0.5 threshold. The resistance rate has shifted. Since both CUSUM and BOCPD fired, the alert is upgraded to HIGH.

8. **Spatiotemporal Clustering** (Layer 2b, Flink) checks: 3 of the 5 resistant isolates came from ICU beds 4, 6, and 8 within the past 5 days. Emits a cluster alert suggesting possible transmission.

9. **ML Predictor** (Layer 2c, batch) already has a prediction for E. coli ciprofloxacin resistance at this facility: 38% probability, up from 22% three months ago. SHAP shows "ICU ward (+12%), hospital-acquired (+8%), recent facility trend (+15%)."

10. **Knowledge Graph** (Layer 2c) contains: E. coli at this facility frequently carries qnrB (fluoroquinolone resistance gene, 34% prevalence from recent WGS data). qnrB co-occurs with bla-CTX-M-15 (ESBL gene) in 78% of cases, meaning third-generation cephalosporin resistance is likely too.

11. **Dashboard** (Layer 4) shows the HIGH alert in red. The infection control nurse sees the spatiotemporal cluster and initiates contact precautions for ICU beds 4-8.

12. **Stewardship pharmacist** asks the agentic layer: "A new ICU patient has a suspected E. coli bloodstream infection. What should we prescribe?"

13. **Claude** (Layer 3) calls `recommend_empiric_therapy` with the context. The tool internally calls: antibiogram query (E. coli %S for all antibiotics), ML prediction (per-antibiotic resistance probabilities), knowledge graph traversal (qnrB + CTX-M-15 prevalence → fluoroquinolones and 3rd-gen cephalosporins compromised), guideline check (WHO BSI guidelines).

14. **Claude responds**: "Based on your facility's data, I'd recommend considering meropenem (predicted susceptibility 96%, AWaRe: Watch) or piperacillin-tazobactam (predicted susceptibility 89%, AWaRe: Watch) for this ICU patient. Ciprofloxacin resistance at your facility has reached 38% for E. coli — a HIGH alert was triggered today. Your facility's WGS data shows 34% qnrB prevalence in E. coli, which also frequently co-occurs with ESBL genes, so third-generation cephalosporins like ceftriaxone are also likely compromised. I'd suggest piperacillin-tazobactam as first choice to avoid unnecessary carbapenem use, with meropenem as backup if clinical response is poor. De-escalate once culture sensitivities return."

15. **Audit log** records every tool call, every data source, every recommendation, with full provenance.

---

## 8. Complete Tech Stack Summary

| Layer | Component | Technology | Language | Why |
|---|---|---|---|---|
| L1 | Parsers | FastAPI | Python | Fast async REST endpoints, easy to extend |
| L1 | Event bus | Apache Kafka (MSK) | N/A | Durable, ordered, scalable event streaming |
| L1 | Schema management | Apache Avro + Confluent Schema Registry | N/A | Type safety, backward-compatible evolution |
| L1 | Time-series DB | TimescaleDB (PostgreSQL extension) | SQL | Time-based partitioning, continuous aggregates, 90% compression |
| L2 | Stream processing | Apache Flink (PyFlink) | Python | Stateful stream processing with event-time semantics |
| L2 | Breakpoint engine | Custom (in Flink) | Python | EUCAST/CLSI classification with version pinning |
| L2 | Outbreak detection | Binary CUSUM + BOCPD (in Flink) | Python | Complementary detection of expected and novel resistance shifts |
| L2 | ML prediction | XGBoost + temporal transformer | Python | Tabular features + temporal drift detection |
| L2 | Explainability | SHAP | Python | Feature importance for clinician trust |
| L2 | Knowledge graph | Neo4j | Cypher | Organism-gene-mechanism-antibiotic reasoning |
| L2 | Batch processing | Celery + Redis | Python | Scheduled tasks (antibiograms, GLASS exports, model retraining) |
| L2 | Eval harness | Claude-as-judge | Python | Quality gate for recommendations |
| L3 | Agentic service | FastAPI + Claude API | Python | LLM tool-calling for clinical decision support |
| L3 | Tool orchestration | Anthropic tool_use | Python | Structured tool calls with typed inputs/outputs |
| L4 | API gateway | Spring Boot 3.2 | Java 21 | Auth, multi-tenancy, routing (your core strength) |
| L4 | Dashboard | React 18 + D3 + Recharts | TypeScript | Real-time surveillance visualizations |
| L4 | PDF generation | ReportLab | Python | Antibiogram and report PDFs |
| L4 | FHIR outbound | HAPI FHIR | Java | EHR integration via HL7 FHIR R4 |
| Infra | Container orchestration | Kubernetes (EKS) | YAML | Production deployment and scaling |
| Infra | IaC | Terraform | HCL | AWS infrastructure provisioning |
| Infra | CI/CD | GitHub Actions | YAML | Path-filtered monorepo workflows |
| Infra | Monitoring | Prometheus + Grafana | N/A | Metrics and dashboards |
| Infra | Tracing | OpenTelemetry | N/A | Distributed tracing across event pipeline |

---

## Monorepo Structure

```
amr-sentinel/
├── services/
│   ├── ingestion/              # Python/FastAPI
│   │   ├── parsers/
│   │   │   ├── whonet.py
│   │   │   ├── fhir_r4.py
│   │   │   ├── csv_mapper.py
│   │   │   └── wgs_pipeline.py
│   │   ├── validators/
│   │   │   ├── isolate_validator.py
│   │   │   └── deidentify.py
│   │   ├── schemas/            # Avro schema definitions
│   │   │   └── validated_isolate.avsc
│   │   ├── main.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── intelligence/           # Python/FastAPI + Flink + Celery
│   │   ├── breakpoints/
│   │   │   ├── engine.py       # SIR classification core
│   │   │   ├── loader.py       # AMR R package breakpoint CSV loader
│   │   │   └── aware.py        # AWaRe classification
│   │   ├── antibiogram/
│   │   │   ├── generator.py    # CLSI M39 antibiogram computation
│   │   │   └── pdf_export.py   # ReportLab PDF generation
│   │   ├── surveillance/
│   │   │   ├── cusum.py        # Binary CUSUM implementation
│   │   │   ├── bocpd.py        # Bayesian Online Changepoint Detection
│   │   │   ├── ensemble.py     # CUSUM + BOCPD alert fusion
│   │   │   └── clustering.py   # Spatiotemporal cluster detection
│   │   ├── ml/
│   │   │   ├── resistance_predictor.py   # XGBoost model
│   │   │   ├── temporal_transformer.py   # Temporal trend model
│   │   │   ├── ensemble.py               # Model combination
│   │   │   ├── train.py                  # Training pipeline
│   │   │   └── eval_harness.py           # Claude-as-judge evaluator
│   │   ├── glass/
│   │   │   ├── ris_generator.py
│   │   │   ├── sample_generator.py
│   │   │   └── quality_checker.py
│   │   ├── knowledge_graph/
│   │   │   ├── schema.cypher   # Neo4j schema definition
│   │   │   ├── loader.py       # CARD/NCBI/ATC data loader
│   │   │   └── queries.py      # Common Cypher query templates
│   │   ├── flink_jobs/
│   │   │   ├── classification_job.py   # Breakpoint + AWaRe (PyFlink)
│   │   │   └── surveillance_job.py     # CUSUM + BOCPD + clustering (PyFlink)
│   │   ├── tasks.py            # Celery task definitions
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── agentic/                # Python/FastAPI
│   │   ├── tools/
│   │   │   ├── empiric_therapy.py
│   │   │   ├── predict_resistance.py
│   │   │   ├── outbreak_alerts.py
│   │   │   ├── antibiogram_query.py
│   │   │   ├── guideline_check.py
│   │   │   ├── kg_traversal.py
│   │   │   └── deescalation.py
│   │   ├── agent.py            # Claude API orchestration loop
│   │   ├── safety.py           # Disclaimer generation, confidence scoring
│   │   ├── main.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── gateway/                # Java/Spring Boot
│       ├── src/main/java/org/amrsentinel/gateway/
│       │   ├── auth/           # JWT authentication
│       │   ├── proxy/          # Service routing
│       │   ├── multitenancy/   # Facility-level data isolation
│       │   └── audit/          # Request/response audit logging
│       ├── pom.xml
│       └── Dockerfile
│
├── frontend/                   # React/TypeScript
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard/
│   │   │   ├── Antibiogram/
│   │   │   ├── AlertsBoard/
│   │   │   ├── ChatInterface/  # Agentic query interface
│   │   │   └── GLASSExport/
│   │   ├── hooks/
│   │   ├── services/
│   │   └── App.tsx
│   ├── package.json
│   └── Dockerfile
│
├── terraform/
│   ├── modules/
│   └── environments/
│
├── data/
│   ├── breakpoints/            # EUCAST/CLSI breakpoint tables
│   ├── aware/                  # WHO AWaRe classification
│   ├── card/                   # CARD database exports
│   └── atlas/                  # ATLAS training data (not committed — downloaded at train time)
│
├── docs/
│   ├── architecture.md
│   ├── api-spec.yaml           # OpenAPI 3.0 specification
│   └── deployment.md
│
├── .github/workflows/
│   ├── ingestion.yml
│   ├── intelligence.yml
│   ├── gateway.yml
│   ├── agentic.yml
│   ├── dashboard.yml
│   └── infrastructure.yml
│
├── docker-compose.yml          # Local development stack
├── CLAUDE.md                   # Claude Code continuity doc
└── README.md
```

---

*This document is the complete technical reference for AMR Sentinel v2. Every component, every technology choice, and every implementation detail is covered. Use it as the foundation for the Vivli challenge expression of interest, the arXiv paper, and conversations with potential collaborators like Dr. Varun Kothamachu.*
