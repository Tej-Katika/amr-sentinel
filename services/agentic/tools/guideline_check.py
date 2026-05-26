"""check_guideline_grounding tool.

Lightweight implementation: an in-memory guideline table for the most common
infection sites. A real deployment would replace this with a curated database
of WHO/IDSA recommendations.
"""
from __future__ import annotations

from .context import ToolContext


DEFINITION = {
    "name": "check_guideline_grounding",
    "description": (
        "Validate a proposed antibiotic choice against published clinical guidelines "
        "(WHO, IDSA, or local formulary). Returns concordance status and the specific "
        "guideline recommendation."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "antibiotic":      {"type": "string"},
            "organism":        {"type": "string"},
            "infection_site":  {"type": "string"},
            "guideline_source": {
                "type": "string",
                "enum": ["WHO", "IDSA", "LOCAL", "ALL"],
                "default": "ALL",
            },
        },
        "required": ["antibiotic", "organism", "infection_site"],
    },
}


# Minimal seed; real implementation pulls from a curated DB
_GUIDELINES = [
    {
        "source": "IDSA",
        "infection_site": "urinary_tract",
        "first_line": ["Nitrofurantoin", "Trimethoprim/sulfamethoxazole", "Fosfomycin"],
        "alt_line":   ["Ciprofloxacin", "Levofloxacin"],
        "note": "Empiric therapy for uncomplicated UTI in non-pregnant women",
        "strength": "strong",
    },
    {
        "source": "IDSA",
        "infection_site": "bloodstream",
        "first_line": ["Piperacillin/tazobactam", "Meropenem"],
        "alt_line":   ["Ceftazidime", "Cefepime"],
        "note": "Empiric therapy for sepsis pending cultures (broad-spectrum coverage)",
        "strength": "strong",
    },
    {
        "source": "WHO",
        "infection_site": "respiratory",
        "first_line": ["Amoxicillin", "Amoxicillin/clavulanate"],
        "alt_line":   ["Ceftriaxone", "Azithromycin"],
        "note": "Empiric therapy for community-acquired pneumonia",
        "strength": "strong",
    },
]


async def run(input: dict, ctx: ToolContext) -> dict:
    site = input["infection_site"].lower()
    abx = input["antibiotic"].lower()
    source_filter = input.get("guideline_source", "ALL")

    matches = [g for g in _GUIDELINES if g["infection_site"] == site]
    if source_filter != "ALL":
        matches = [g for g in matches if g["source"] == source_filter]

    if not matches:
        return {"concordance": "no_guidance", "matches": []}

    out = []
    for g in matches:
        if abx in (a.lower() for a in g["first_line"]):
            concord = "concordant_first_line"
        elif abx in (a.lower() for a in g["alt_line"]):
            concord = "concordant_alternative"
        else:
            concord = "discordant"
        out.append({**g, "concordance": concord})
    return {"organism": input["organism"], "antibiotic": input["antibiotic"], "matches": out}
