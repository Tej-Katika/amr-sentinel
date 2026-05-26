"""query_antibiogram tool."""
from __future__ import annotations

from .context import ToolContext


DEFINITION = {
    "name": "query_antibiogram",
    "description": (
        "Return the current antibiogram (percent susceptible per organism+antibiotic) "
        "for a facility. Filterable by organism, time period, and stratification."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "organism": {"type": "string", "description": "Filter by specific organism (optional)"},
            "period_months": {"type": "integer", "default": 12, "description": "Time period in months"},
            "stratification": {
                "type": "string",
                "enum": ["ALL", "ICU", "NON_ICU", "BLOOD", "URINE"],
                "default": "ALL",
            },
        },
        "required": [],
    },
}


async def run(input: dict, ctx: ToolContext) -> dict:
    params = {"facility_id": ctx.facility_id,
              "period_months": input.get("period_months", 12),
              "stratification": input.get("stratification", "ALL")}
    if input.get("organism"):
        params["organism"] = input["organism"]

    async with ctx.http() as client:
        resp = await client.get("/antibiogram", params=params)
        resp.raise_for_status()
        return resp.json()
