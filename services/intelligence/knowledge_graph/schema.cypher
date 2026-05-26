// AMR Sentinel — Neo4j knowledge graph schema
// Apply with: cypher-shell -f schema.cypher

// ============================================
// Constraints
// ============================================
CREATE CONSTRAINT organism_taxid IF NOT EXISTS
FOR (o:Organism) REQUIRE o.ncbi_taxid IS UNIQUE;

CREATE CONSTRAINT antibiotic_atc IF NOT EXISTS
FOR (a:Antibiotic) REQUIRE a.atc_code IS UNIQUE;

CREATE CONSTRAINT gene_name IF NOT EXISTS
FOR (g:ResistanceGene) REQUIRE g.gene_name IS UNIQUE;

CREATE CONSTRAINT mechanism_name IF NOT EXISTS
FOR (m:ResistanceMechanism) REQUIRE m.name IS UNIQUE;

CREATE CONSTRAINT drug_class_name IF NOT EXISTS
FOR (d:DrugClass) REQUIRE d.name IS UNIQUE;

CREATE CONSTRAINT facility_id IF NOT EXISTS
FOR (f:Facility) REQUIRE f.facility_id IS UNIQUE;

CREATE CONSTRAINT guideline_id IF NOT EXISTS
FOR (g:Guideline) REQUIRE g.guideline_id IS UNIQUE;

// ============================================
// Indexes
// ============================================
CREATE INDEX organism_name IF NOT EXISTS FOR (o:Organism) ON (o.name);
CREATE INDEX antibiotic_name IF NOT EXISTS FOR (a:Antibiotic) ON (a.name);
CREATE INDEX gene_family IF NOT EXISTS FOR (g:ResistanceGene) ON (g.gene_family);
