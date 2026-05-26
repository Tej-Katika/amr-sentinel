"""Agentic tools — each module exposes:

    DEFINITION : dict          # Anthropic tool spec (name, description, input_schema)
    async def run(input: dict, ctx: ToolContext) -> dict   # implementation
"""
from . import (
    antibiogram_query,
    deescalation,
    empiric_therapy,
    guideline_check,
    kg_traversal,
    outbreak_alerts,
    predict_resistance,
)

ALL = [
    empiric_therapy,
    predict_resistance,
    outbreak_alerts,
    antibiogram_query,
    guideline_check,
    kg_traversal,
    deescalation,
]

DEFINITIONS = [m.DEFINITION for m in ALL]
DISPATCH = {m.DEFINITION["name"]: m.run for m in ALL}
