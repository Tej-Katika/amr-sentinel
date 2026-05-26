"""Reusable Cypher query templates for the agentic layer's KG tool."""
from __future__ import annotations

from typing import Optional

from neo4j import Driver

from .loader import get_driver


def organism_genes(driver: Driver, organism_name: str, facility_id: Optional[str] = None) -> list[dict]:
    """Genes carried by an organism, optionally filtered to facility-prevalent ones."""
    cypher = """
        MATCH (o:Organism)-[:CARRIES]->(g:ResistanceGene)
        WHERE toLower(o.name) = toLower($organism)
        OPTIONAL MATCH (g)-[:CONFERS]->(m:ResistanceMechanism)-[:ACTS_AGAINST]->(d:DrugClass)
        RETURN g.gene_name AS gene,
               g.gene_family AS family,
               g.description AS description,
               collect(DISTINCT m.name) AS mechanisms,
               collect(DISTINCT d.name) AS drug_classes
        ORDER BY gene
    """
    with driver.session() as s:
        return [dict(r) for r in s.run(cypher, organism=organism_name)]


def organism_resistance_profile(driver: Driver, organism_name: str, facility_id: str) -> list[dict]:
    """Phenotypic resistance rates for the organism at a facility."""
    cypher = """
        MATCH (o:Organism)-[r:PHENOTYPIC_RESISTANCE]->(a:Antibiotic)
        WHERE toLower(o.name) = toLower($organism)
          AND r.facility_id = $facility_id
        RETURN a.atc_code AS atc,
               a.name     AS antibiotic,
               a.aware_category AS aware,
               r.rate     AS resistance_rate,
               r.n        AS n
        ORDER BY r.rate DESC
    """
    with driver.session() as s:
        return [dict(r) for r in s.run(cypher, organism=organism_name, facility_id=facility_id)]


def gene_mechanisms(driver: Driver, gene: str) -> list[dict]:
    cypher = """
        MATCH (g:ResistanceGene {gene_name: $gene})-[:CONFERS]->(m:ResistanceMechanism)
        OPTIONAL MATCH (m)-[:ACTS_AGAINST]->(d:DrugClass)
        RETURN m.name AS mechanism, collect(DISTINCT d.name) AS drug_classes
    """
    with driver.session() as s:
        return [dict(r) for r in s.run(cypher, gene=gene)]


def mechanism_drugs_affected(driver: Driver, mechanism: str) -> list[dict]:
    cypher = """
        MATCH (m:ResistanceMechanism {name: $mechanism})-[:ACTS_AGAINST]->(d:DrugClass)
        OPTIONAL MATCH (d)-[:CONTAINS]->(a:Antibiotic)
        RETURN d.name AS drug_class, collect(DISTINCT a.name) AS antibiotics
    """
    with driver.session() as s:
        return [dict(r) for r in s.run(cypher, mechanism=mechanism)]


def gene_cooccurrence(driver: Driver, gene: str) -> list[dict]:
    cypher = """
        MATCH (g:ResistanceGene {gene_name: $gene})-[r:CO_OCCURS_WITH]-(g2:ResistanceGene)
        RETURN g2.gene_name AS partner, r.frequency AS frequency
        ORDER BY frequency DESC
    """
    with driver.session() as s:
        return [dict(r) for r in s.run(cypher, gene=gene)]
