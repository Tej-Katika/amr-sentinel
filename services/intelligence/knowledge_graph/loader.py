"""Load reference data into the AMR knowledge graph.

Loads:
    - Organisms (NCBI taxonomy subset)
    - Antibiotics + ATC + AWaRe + drug classes
    - Resistance genes (CARD subset, seed only — full CARD load via download_card.py)
    - Resistance mechanisms
    - Phenotypic resistance edges (computed from TimescaleDB)
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from neo4j import GraphDatabase, Driver

log = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parents[3] / "services" / "ingestion" / "config"
AWARE_CSV = Path(__file__).resolve().parents[3] / "data" / "aware" / "aware_2023.csv"
SEED_CARD = Path(__file__).resolve().parent / "card_seed.json"


def get_driver() -> Driver:
    return GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "amrsentinel_dev")),
    )


def load_organisms(driver: Driver) -> int:
    with (CONFIG_DIR / "organism_taxonomy.json").open() as f:
        data = json.load(f)
    rows = list(data["by_whonet_code"].values())
    with driver.session() as s:
        s.run(
            """
            UNWIND $rows AS row
            MERGE (o:Organism {ncbi_taxid: row.taxid})
            SET o.name = row.name, o.gram_stain = row.gram_stain, o.family = row.family
            """,
            rows=rows,
        )
    return len(rows)


def load_antibiotics(driver: Driver) -> int:
    import csv

    with (CONFIG_DIR / "antibiotic_atc.json").open() as f:
        data = json.load(f)
    aware: dict[str, str] = {}
    if AWARE_CSV.exists():
        with AWARE_CSV.open() as f:
            for row in csv.DictReader(f):
                aware[row["atc_code"]] = row["aware_category"]

    rows = []
    drug_classes: set[str] = set()
    for code, payload in data["by_whonet_code"].items():
        rows.append({
            "atc": payload["atc"],
            "name": payload["name"],
            "drug_class": payload["drug_class"],
            "aware": aware.get(payload["atc"]),
        })
        drug_classes.add(payload["drug_class"])

    with driver.session() as s:
        s.run(
            """
            UNWIND $classes AS cls
            MERGE (d:DrugClass {name: cls})
            """,
            classes=list(drug_classes),
        )
        s.run(
            """
            UNWIND $rows AS row
            MERGE (a:Antibiotic {atc_code: row.atc})
            SET a.name = row.name, a.aware_category = row.aware
            WITH a, row
            MATCH (d:DrugClass {name: row.drug_class})
            MERGE (d)-[:CONTAINS]->(a)
            """,
            rows=rows,
        )
    return len(rows)


def load_resistance_genes(driver: Driver, path: Optional[Path] = None) -> int:
    """Load a curated CARD subset (seed). For the full CARD database run
    scripts/download_card.py and re-run with the larger file."""
    path = path or SEED_CARD
    if not path.exists():
        log.warning("CARD seed file not found at %s; skipping gene load", path)
        return 0
    with path.open() as f:
        rows = json.load(f)

    with driver.session() as s:
        for row in rows:
            s.run(
                """
                MERGE (g:ResistanceGene {gene_name: $gene})
                SET g.gene_family = $family,
                    g.description = $description
                WITH g
                UNWIND $mechanisms AS m
                MERGE (mech:ResistanceMechanism {name: m})
                MERGE (g)-[:CONFERS]->(mech)
                WITH g, mech
                UNWIND $drug_classes AS dc
                MERGE (d:DrugClass {name: dc})
                MERGE (mech)-[:ACTS_AGAINST]->(d)
                WITH g
                UNWIND $organisms AS org_taxid
                MATCH (o:Organism {ncbi_taxid: org_taxid})
                MERGE (o)-[:CARRIES]->(g)
                """,
                gene=row["gene"],
                family=row.get("family"),
                description=row.get("description"),
                mechanisms=row.get("mechanisms", []),
                drug_classes=row.get("drug_classes", []),
                organisms=row.get("organisms", []),
            )
    return len(rows)


def load_phenotypic_resistance(driver: Driver, conn) -> int:
    """Compute phenotypic resistance rates from TimescaleDB and store as edges
    Organism-[:PHENOTYPIC_RESISTANCE]->Antibiotic."""
    from psycopg2.extras import RealDictCursor

    sql = """
        SELECT facility_id, organism_taxid, organism_name,
               antibiotic_atc,
               COUNT(*) FILTER (WHERE sir_classification='R')::float / NULLIF(COUNT(*),0) AS rate,
               COUNT(*) AS n
        FROM isolate_events
        WHERE collection_date >= NOW() - INTERVAL '12 months'
          AND sir_classification IS NOT NULL
        GROUP BY facility_id, organism_taxid, organism_name, antibiotic_atc
        HAVING COUNT(*) >= 30;
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql)
        rows = cur.fetchall()

    with driver.session() as s:
        for row in rows:
            s.run(
                """
                MERGE (o:Organism {ncbi_taxid: $taxid})
                ON CREATE SET o.name = $name
                MERGE (a:Antibiotic {atc_code: $atc})
                MERGE (o)-[r:PHENOTYPIC_RESISTANCE {facility_id: $facility, period: 'rolling_12m'}]->(a)
                SET r.rate = $rate, r.n = $n, r.updated_at = datetime()
                """,
                taxid=row["organism_taxid"],
                name=row["organism_name"],
                atc=row["antibiotic_atc"],
                facility=row["facility_id"],
                rate=float(row["rate"] or 0),
                n=row["n"],
            )
    return len(rows)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    driver = get_driver()
    try:
        log.info("Loaded %d organisms", load_organisms(driver))
        log.info("Loaded %d antibiotics", load_antibiotics(driver))
        log.info("Loaded %d resistance genes", load_resistance_genes(driver))
    finally:
        driver.close()


if __name__ == "__main__":
    main()
