"""get_outbreak_alerts tool."""
from __future__ import annotations

from .context import ToolContext


DEFINITION = {
    "name": "get_outbreak_alerts",
    "description": "Retrieve active CUSUM/BOCPD outbreak alerts for the user's facility, with severity levels and trend context.",
    "input_schema": {
        "type": "object",
        "properties": {
            "severity_filter": {
                "type": "string",
                "enum": ["HIGH", "MODERATE", "INVESTIGATE", "ALL"],
                "default": "ALL",
            },
            "days_back": {"type": "integer", "default": 30},
        },
        "required": [],
    },
}


async def run(input: dict, ctx: ToolContext) -> dict:
    params = {
        "facility_id": ctx.facility_id,
        "severity": input.get("severity_filter", "ALL"),
        "days_back": input.get("days_back", 30),
    }
    async with ctx.http() as client:
        r = await client.get("/alerts", params=params)
        r.raise_for_status()
        return r.json()
