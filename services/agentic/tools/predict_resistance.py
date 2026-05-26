"""predict_resistance tool."""
from __future__ import annotations

from .context import ToolContext


DEFINITION = {
    "name": "predict_resistance",
    "description": (
        "Get the ML ensemble prediction for resistance probability of a specific "
        "organism+antibiotic combination at the user's facility, with SHAP-based "
        "feature importance explaining why."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "organism": {"type": "string", "description": "Organism name"},
            "antibiotic": {"type": "string", "description": "Antibiotic name"},
            "patient_context": {
                "type": "object",
                "properties": {
                    "age_group": {"type": "string"},
                    "ward_type": {"type": "string"},
                    "infection_origin": {"type": "string"},
                    "specimen_type": {"type": "string"},
                },
            },
        },
        "required": ["organism", "antibiotic"],
    },
}


async def run(input: dict, ctx: ToolContext) -> dict:
    organism = input["organism"]
    antibiotic = input["antibiotic"]

    async with ctx.http() as client:
        # Resolve organism+antibiotic to taxid+ATC via the antibiogram (which already has them)
        ab = await client.get("/antibiogram", params={
            "facility_id": ctx.facility_id, "period_months": 12, "stratification": "ALL",
            "organism": organism,
        })
        ab.raise_for_status()
        cells = ab.json().get("cells", [])
        cell = next((c for c in cells if c["antibiotic_name"].lower() == antibiotic.lower()), None)

        if not cell:
            return {
                "error": "no_data",
                "message": f"No isolates of {organism} + {antibiotic} at this facility.",
            }

        ctx_data = input.get("patient_context", {}) or {}
        from datetime import date
        today = date.today()
        try:
            r = await client.post("/predict/resistance", json={
                "organism_taxid":     cell["organism_taxid"],
                "antibiotic_atc":     cell["antibiotic_atc"],
                "drug_class":         cell.get("drug_class"),
                "facility_id":        ctx.facility_id,
                "country_iso3":       "USA",  # filled by gateway in production
                "region":             "North America",
                "specimen_type":      ctx_data.get("specimen_type"),
                "patient_age_group":  ctx_data.get("age_group"),
                "patient_sex":        None,
                "ward_type":          ctx_data.get("ward_type"),
                "infection_origin":   (ctx_data.get("infection_origin") or "UNKNOWN").upper(),
                "year":               today.year,
                "month":              today.month,
                "facility_baseline_rate": (cell["n_total"] - cell["n_susceptible"]) / max(cell["n_total"], 1),
                "n_observations":     cell["n_total"],
            })
            if r.status_code == 503:
                return {
                    "model_status": "no_model_trained",
                    "fallback_observed_resistance_rate":
                        (cell["n_total"] - cell["n_susceptible"]) / max(cell["n_total"], 1),
                    "n": cell["n_total"],
                }
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            return {"error": "predict_failed", "message": str(exc)}
