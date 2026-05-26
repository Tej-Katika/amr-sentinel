"""recommend_empiric_therapy tool.

Composes the antibiogram + ML predictions + AWaRe + guidelines + KG into a
ranked list of antibiotic options. Most of the synthesis happens in Claude;
this tool just gathers the structured inputs.
"""
from __future__ import annotations

from .context import ToolContext


DEFINITION = {
    "name": "recommend_empiric_therapy",
    "description": (
        "Recommend ranked antibiotic options for empiric therapy based on the "
        "facility's antibiogram, ML resistance predictions, WHO AWaRe classification, "
        "knowledge graph context, and applicable clinical guidelines. Use this when a "
        "clinician asks what to prescribe before culture results are available."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "organism": {"type": "string", "description": "Suspected/confirmed organism (optional)"},
            "infection_site": {
                "type": "string",
                "enum": ["urinary_tract", "bloodstream", "respiratory",
                         "skin_soft_tissue", "intra_abdominal", "CNS", "bone_joint"],
            },
            "patient_age_group": {"type": "string"},
            "ward_type": {
                "type": "string",
                "enum": ["ICU", "general", "surgical", "pediatric", "neonatal", "outpatient"],
            },
            "infection_origin": {"type": "string", "enum": ["community", "hospital"]},
        },
        "required": ["infection_site"],
    },
}


SITE_TO_LIKELY_ORGANISMS = {
    "urinary_tract":     ["Escherichia coli", "Klebsiella pneumoniae"],
    "bloodstream":       ["Escherichia coli", "Staphylococcus aureus", "Klebsiella pneumoniae"],
    "respiratory":       ["Streptococcus pneumoniae", "Klebsiella pneumoniae", "Pseudomonas aeruginosa"],
    "skin_soft_tissue":  ["Staphylococcus aureus", "Streptococcus pneumoniae"],
    "intra_abdominal":   ["Escherichia coli", "Klebsiella pneumoniae"],
    "CNS":               ["Streptococcus pneumoniae"],
    "bone_joint":        ["Staphylococcus aureus"],
}


async def run(input: dict, ctx: ToolContext) -> dict:
    site = input["infection_site"]
    organism = input.get("organism")
    organisms_to_check = [organism] if organism else SITE_TO_LIKELY_ORGANISMS.get(site, [])

    async with ctx.http() as client:
        # 1) Antibiogram
        ab_resp = await client.get("/antibiogram", params={
            "facility_id": ctx.facility_id, "period_months": 12, "stratification": "ALL",
        })
        ab_resp.raise_for_status()
        antibiogram = ab_resp.json()

        # 2) Active high-severity alerts
        alerts_resp = await client.get("/alerts", params={
            "facility_id": ctx.facility_id, "severity": "ALL", "days_back": 30,
        })
        alerts_resp.raise_for_status()
        alerts = alerts_resp.json()

        # 3) Knowledge graph profile (best-effort)
        profiles = []
        for org in organisms_to_check:
            try:
                kg_resp = await client.get(
                    f"/kg/organism/{org}/profile",
                    params={"facility_id": ctx.facility_id},
                )
                if kg_resp.status_code == 200:
                    profiles.append(kg_resp.json())
            except Exception:
                continue

    # Rank candidate antibiotics by %S (descending) for the likely organisms
    candidates: list[dict] = []
    for org in organisms_to_check:
        for cell in antibiogram.get("cells", []):
            if cell["organism_name"].lower() != org.lower():
                continue
            if cell.get("percent_susceptible") is None:
                continue
            candidates.append({
                "organism": cell["organism_name"],
                "antibiotic": cell["antibiotic_name"],
                "atc": cell["antibiotic_atc"],
                "drug_class": cell.get("drug_class"),
                "aware_category": cell.get("aware_category"),
                "percent_susceptible": cell["percent_susceptible"],
                "n_isolates": cell["n_total"],
            })
    candidates.sort(key=lambda c: (-c["percent_susceptible"], c["aware_category"] or "ZZ"))

    return {
        "facility_id": ctx.facility_id,
        "infection_site": site,
        "organisms_considered": organisms_to_check,
        "ranked_candidates": candidates[:15],
        "active_alerts": alerts.get("alerts", [])[:10],
        "kg_profiles": profiles,
        "antibiogram_period": {
            "start": antibiogram.get("period_start"),
            "end":   antibiogram.get("period_end"),
        },
    }
