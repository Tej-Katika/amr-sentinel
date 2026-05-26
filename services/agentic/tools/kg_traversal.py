"""traverse_knowledge_graph tool."""
from __future__ import annotations

from .context import ToolContext


DEFINITION = {
    "name": "traverse_knowledge_graph",
    "description": (
        "Query the AMR knowledge graph to explore relationships between organisms, "
        "resistance genes, mechanisms, and antibiotics. Use for mechanistic questions "
        "like 'what resistance genes does this organism carry'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query_type": {
                "type": "string",
                "enum": [
                    "organism_genes",
                    "organism_resistance_profile",
                ],
            },
            "organism": {"type": "string"},
        },
        "required": ["query_type"],
    },
}


async def run(input: dict, ctx: ToolContext) -> dict:
    query_type = input["query_type"]
    organism = input.get("organism")
    if not organism:
        return {"error": "organism is required"}

    async with ctx.http() as client:
        if query_type == "organism_genes":
            r = await client.get(f"/kg/organism/{organism}/genes",
                                 params={"facility_id": ctx.facility_id})
        else:
            r = await client.get(f"/kg/organism/{organism}/profile",
                                 params={"facility_id": ctx.facility_id})
        r.raise_for_status()
        return r.json()
