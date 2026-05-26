"""Safety layer for agentic responses.

Every recommendation gets a disclaimer, a confidence score, and provenance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DISCLAIMER = (
    "\n\n---\n"
    "*Decision support only. Clinical judgment must always override AI recommendations. "
    "AMR Sentinel surfaces local resistance patterns and guideline grounding; the "
    "treating clinician retains responsibility for the prescribing decision.*"
)

WATCH_RESERVE_WARNING = (
    "\n\n**AWaRe stewardship note**: This recommendation includes Watch or "
    "Reserve antibiotics. Use the narrowest effective agent — confirm there is no "
    "Access alternative with adequate susceptibility before escalating."
)


@dataclass
class Provenance:
    facility_id: str
    tools_called: list[str] = field(default_factory=list)
    tool_inputs: dict[str, Any] = field(default_factory=dict)
    tool_results_summary: dict[str, Any] = field(default_factory=dict)


def confidence_from_tool_results(tool_results: list[dict]) -> float:
    """Heuristic confidence based on the data each tool returned.

    Floor is 0.3 (low confidence — always tell clinicians the data is thin).
    """
    score = 0.3
    for result in tool_results:
        body = result.get("content")
        if not body:
            continue

        # Antibiogram cells
        cells = (body.get("cells") if isinstance(body, dict) else None) or []
        if cells:
            n_with_data = sum(1 for c in cells if c.get("percent_susceptible") is not None)
            if n_with_data >= 5:
                score += 0.2

        # Ranked candidates
        candidates = (body.get("ranked_candidates") if isinstance(body, dict) else None) or []
        if candidates:
            avg_n = sum(c.get("n_isolates", 0) for c in candidates) / max(len(candidates), 1)
            if avg_n >= 100:
                score += 0.2
            elif avg_n >= 30:
                score += 0.1

        # Predictions
        if isinstance(body, dict) and "predicted_rate" in body:
            score += 0.1

    return round(min(score, 0.95), 2)


def append_disclaimer(text: str, mentions_watch_reserve: bool) -> str:
    out = text
    if mentions_watch_reserve:
        out += WATCH_RESERVE_WARNING
    out += DISCLAIMER
    return out


def detect_watch_reserve(response_text: str, tool_results: list[dict]) -> bool:
    text_lower = response_text.lower()
    keywords = ["meropenem", "imipenem", "ertapenem", "vancomycin", "colistin",
                "linezolid", "daptomycin", "tigecycline", "ceftriaxone",
                "piperacillin", "ciprofloxacin", "levofloxacin"]
    if any(k in text_lower for k in keywords):
        return True
    for result in tool_results:
        body = result.get("content")
        if isinstance(body, dict):
            for c in body.get("ranked_candidates", []) or []:
                if c.get("aware_category") in {"WATCH", "RESERVE"}:
                    return True
    return False
