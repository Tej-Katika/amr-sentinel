"""advise_de_escalation tool."""
from __future__ import annotations

from .context import ToolContext


DEFINITION = {
    "name": "advise_de_escalation",
    "description": (
        "Given a patient's current broad-spectrum therapy and their now-available "
        "lab results, recommend narrower-spectrum alternatives for antibiotic "
        "de-escalation."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "current_antibiotic": {"type": "string"},
            "organism":           {"type": "string"},
            "sir_results": {
                "type": "object",
                "additionalProperties": {"type": "string", "enum": ["S", "I", "R"]},
            },
            "infection_site": {"type": "string"},
        },
        "required": ["current_antibiotic", "organism", "sir_results"],
    },
}


# Rough spectrum ordering — lower index = narrower
SPECTRUM_RANK = [
    "Penicillin G", "Ampicillin", "Amoxicillin", "Oxacillin",
    "Nitrofurantoin", "Trimethoprim/sulfamethoxazole",
    "Cefoxitin",
    "Ceftriaxone", "Ceftazidime",
    "Cefepime",
    "Piperacillin/tazobactam", "Amoxicillin/clavulanate",
    "Ertapenem", "Meropenem", "Imipenem",
    "Ciprofloxacin", "Levofloxacin",
    "Vancomycin", "Linezolid", "Daptomycin", "Tigecycline", "Colistin",
]


def _rank(name: str) -> int:
    try:
        return SPECTRUM_RANK.index(name)
    except ValueError:
        return len(SPECTRUM_RANK)


async def run(input: dict, ctx: ToolContext) -> dict:
    current = input["current_antibiotic"]
    sir_results = input["sir_results"]

    # Susceptible alternatives
    susceptible = [name for name, sir in sir_results.items() if sir == "S"]
    susceptible.sort(key=_rank)

    current_rank = _rank(current)
    narrower = [{"antibiotic": n, "spectrum_rank": _rank(n)} for n in susceptible
                if _rank(n) < current_rank]

    return {
        "current_antibiotic": current,
        "current_spectrum_rank": current_rank,
        "narrower_susceptible_options": narrower[:5],
        "total_susceptible_alternatives": len(susceptible),
        "all_susceptible": susceptible,
    }
