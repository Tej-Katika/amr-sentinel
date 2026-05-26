#!/usr/bin/env python3
"""Generate synthetic isolate data for testing.

Produces ~10,000 isolate-antibiotic test results across 3 facilities, 5 organisms,
12 antibiotics, spanning 12 months. Embeds two outbreak signals:
    - E. coli + Ciprofloxacin resistance spike at FACILITY_001 (months 9-11)
    - MRSA cluster in FACILITY_001 ICU (last 7 days)

Output: data/sample_data/synthetic_isolates.csv

Usage:
    python scripts/generate_sample_data.py [--n N] [--out PATH]
"""
from __future__ import annotations

import argparse
import csv
import random
import uuid
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

FACILITIES = ["FACILITY_001", "FACILITY_002", "FACILITY_003"]
WARDS = {
    "FACILITY_001": ["WARD_001_ICU", "WARD_001_GEN", "WARD_001_SURG", "WARD_001_PED"],
    "FACILITY_002": ["WARD_002_ICU", "WARD_002_GEN"],
    "FACILITY_003": ["WARD_003_REF"],
}
SPECIMEN_TYPES = ["BLOOD", "URINE", "RESPIRATORY", "WOUND"]
SEX = ["M", "F"]
AGE_GROUPS = ["0-4", "5-14", "15-24", "25-34", "35-44", "45-54", "55-64", "65+"]
ORIGINS = ["COMMUNITY", "HOSPITAL"]

# (taxid, name, gram_stain, base_resistance_profile)
# base_resistance_profile is the baseline P(resistant) per ATC.
ORGANISMS = [
    (562, "Escherichia coli", "NEGATIVE", {
        "J01CA01": 0.55, "J01CR02": 0.30, "J01DD04": 0.20, "J01MA02": 0.20,
        "J01GB03": 0.15, "J01EE01": 0.40, "J01XE01": 0.05, "J01CR05": 0.10,
        "J01DH02": 0.02, "J01XX01": 0.05,
    }),
    (573, "Klebsiella pneumoniae", "NEGATIVE", {
        "J01CR02": 0.40, "J01DD04": 0.30, "J01MA02": 0.25, "J01GB03": 0.20,
        "J01EE01": 0.45, "J01CR05": 0.20, "J01DH02": 0.10, "J01XB01": 0.05,
    }),
    (1280, "Staphylococcus aureus", "POSITIVE", {
        "J01CF04": 0.30, "J01XA01": 0.02, "J01FF01": 0.20, "J01GB03": 0.15,
        "J01XX08": 0.01, "J01EE01": 0.10, "J04AB02": 0.05, "J01MA02": 0.30,
    }),
    (287, "Pseudomonas aeruginosa", "NEGATIVE", {
        "J01DD02": 0.25, "J01DE01": 0.20, "J01MA02": 0.30, "J01GB03": 0.20,
        "J01CR05": 0.15, "J01DH02": 0.10, "J01XB01": 0.05,
    }),
    (470, "Acinetobacter baumannii", "NEGATIVE", {
        "J01DH02": 0.40, "J01DH51": 0.40, "J01CR05": 0.50, "J01MA02": 0.50,
        "J01GB03": 0.40, "J01EE01": 0.45, "J01XB01": 0.10, "J01AA12": 0.20,
    }),
]

# Map ATC to (name, drug_class)
ABX_INFO = {
    "J01CA01": ("Ampicillin", "Aminopenicillins"),
    "J01CR02": ("Amoxicillin/clavulanate", "Beta-lactam/inhibitor"),
    "J01CF04": ("Oxacillin", "Penicillinase-resistant penicillins"),
    "J01CR05": ("Piperacillin/tazobactam", "Beta-lactam/inhibitor"),
    "J01DD04": ("Ceftriaxone", "Cephalosporins (3rd gen)"),
    "J01DD02": ("Ceftazidime", "Cephalosporins (3rd gen)"),
    "J01DE01": ("Cefepime", "Cephalosporins (4th gen)"),
    "J01DH02": ("Meropenem", "Carbapenems"),
    "J01DH51": ("Imipenem", "Carbapenems"),
    "J01MA02": ("Ciprofloxacin", "Fluoroquinolones"),
    "J01GB03": ("Gentamicin", "Aminoglycosides"),
    "J01EE01": ("Trimethoprim/sulfamethoxazole", "Sulfonamides"),
    "J01XA01": ("Vancomycin", "Glycopeptides"),
    "J01XX08": ("Linezolid", "Oxazolidinones"),
    "J01XB01": ("Colistin", "Polymyxins"),
    "J01XE01": ("Nitrofurantoin", "Nitrofurans"),
    "J01FF01": ("Clindamycin", "Lincosamides"),
    "J04AB02": ("Rifampicin", "Rifamycins"),
    "J01XX01": ("Fosfomycin", "Phosphonics"),
    "J01AA12": ("Tigecycline", "Glycylcyclines"),
}

# AWaRe categories
AWARE = {
    "ACCESS": {"J01CA01", "J01CR02", "J01CF04", "J01XE01", "J01XX01", "J01EE01", "J01GB03", "J01FF01"},
    "WATCH": {"J01CR05", "J01DD04", "J01DD02", "J01DE01", "J01DH02", "J01DH51", "J01MA02", "J01XA01", "J04AB02"},
    "RESERVE": {"J01XX08", "J01XB01", "J01AA12"},
}


def aware(atc: str) -> str:
    for cat, codes in AWARE.items():
        if atc in codes:
            return cat
    return "ACCESS"


def mic_for(p_resistant: float, breakpoint: float) -> tuple[float, str]:
    """Sample a MIC value that produces approximately the desired resistance rate.
    Returns (value, sir_label)."""
    if random.random() < p_resistant:
        # Resistant: value above breakpoint
        value = breakpoint * random.uniform(2, 16)
        return round(value, 3), "R"
    else:
        # Susceptible: value at or below breakpoint
        value = breakpoint * random.uniform(0.05, 0.5)
        return round(value, 3), "S"


def generate(n: int, out_path: Path) -> int:
    today = date.today()
    earliest = today - timedelta(days=365)

    rows = []
    for i in range(n):
        facility_id = random.choice(FACILITIES)
        organism = random.choice(ORGANISMS)
        taxid, organism_name, gram, profile = organism

        # Pick a random antibiotic the organism would be tested against
        atc = random.choice(list(profile.keys()))
        abx_name, drug_class = ABX_INFO[atc]
        base_p_r = profile[atc]

        days_ago = random.randint(0, 365)
        coll_date = today - timedelta(days=days_ago)

        # Outbreak signal: E. coli + ciprofloxacin spike at FACILITY_001 in last 90 days
        if (
            facility_id == "FACILITY_001"
            and taxid == 562
            and atc == "J01MA02"
            and days_ago < 90
        ):
            base_p_r = 0.55  # spike from 20% baseline to 55%

        # Outbreak: MRSA in FACILITY_001 ICU last 7 days
        ward_id = random.choice(WARDS[facility_id])
        if (
            facility_id == "FACILITY_001"
            and taxid == 1280
            and atc == "J01CF04"
            and days_ago < 7
        ):
            ward_id = "WARD_001_ICU"
            base_p_r = 0.85

        # Approximate breakpoints (from seed CSV)
        approx_bp = {
            "J01CA01": 8, "J01CR02": 8, "J01CF04": 2, "J01CR05": 16,
            "J01DD04": 2, "J01DD02": 4, "J01DE01": 4, "J01DH02": 8,
            "J01DH51": 8, "J01MA02": 0.5, "J01GB03": 4, "J01EE01": 4,
            "J01XA01": 2, "J01XX08": 4, "J01XB01": 2, "J01XE01": 64,
            "J01FF01": 0.5, "J04AB02": 0.5, "J01XX01": 8, "J01AA12": 0.5,
        }
        bp = approx_bp.get(atc, 8)
        value, sir = mic_for(base_p_r, bp)

        rows.append({
            "event_id": str(uuid.uuid4()),
            "facility_id": facility_id,
            "specimen_id": f"SPEC-{coll_date.isoformat()}-{i:06d}",
            "specimen_type": random.choice(SPECIMEN_TYPES),
            "organism_taxid": taxid,
            "organism_name": organism_name,
            "gram_stain": gram,
            "antibiotic_atc": atc,
            "antibiotic_name": abx_name,
            "drug_class": drug_class,
            "measurement_type": "MIC",
            "measurement_value": value,
            "measurement_comparator": "",
            "sir_classification": sir,
            "breakpoint_standard": "EUCAST",
            "breakpoint_version": "2025.1",
            "aware_category": aware(atc),
            "patient_age_group": random.choice(AGE_GROUPS),
            "patient_sex": random.choice(SEX),
            "ward_id": ward_id,
            "infection_origin": random.choice(ORIGINS),
            "is_first_isolate": True,
            "collection_date": coll_date.isoformat(),
            "ingested_at": coll_date.isoformat() + "T08:00:00Z",
            "classified_at": coll_date.isoformat() + "T08:00:01Z",
            "source_format": "WHONET",
        })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=10000)
    parser.add_argument("--out", default="data/sample_data/synthetic_isolates.csv")
    args = parser.parse_args()

    n = generate(args.n, Path(args.out))
    print(f"Wrote {n} isolate events to {args.out}")


if __name__ == "__main__":
    main()
