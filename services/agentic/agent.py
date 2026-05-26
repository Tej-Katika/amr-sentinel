"""Agent orchestration loop.

Sends queries to Claude with tool definitions, executes tool_use blocks against
the Layer 2 Intelligence service, feeds results back, and synthesizes a final
recommendation with safety disclaimers and provenance.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

import anthropic

from .safety import (
    Provenance,
    append_disclaimer,
    confidence_from_tool_results,
    detect_watch_reserve,
)
from .tools import DEFINITIONS, DISPATCH
from .tools.context import ToolContext

log = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are AMR Sentinel's clinical stewardship assistant. You help \
clinicians make evidence-based antibiotic prescribing decisions using local \
resistance data.

CRITICAL SAFETY RULES:
1. NEVER directly prescribe. Always frame as "recommendations" or "options to consider."
2. ALWAYS state the data provenance (which facility, what time period, how many isolates).
3. ALWAYS flag Watch and Reserve (AWaRe) antibiotics with a clear explanation of why a broader-spectrum agent is being suggested over an Access one.
4. When data is insufficient (< 30 isolates), explicitly say confidence is LOW.
5. NEVER fabricate resistance data. If a tool returns no data, say so.
6. When recommending therapy, list 2-3 ranked options with the rationale for each, not a single "answer."

When answering questions, call the appropriate tools to ground your response in real \
data. Synthesize tool results into clear, actionable clinical guidance. Use markdown \
formatting (bold, bullet lists) for readability."""


MODEL = os.getenv("AGENT_MODEL", "claude-sonnet-4-6")
MAX_TURNS = 6


@dataclass
class AgentResponse:
    recommendation: str
    tools_called: list[str] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    confidence_score: float = 0.0
    data_provenance: dict[str, Any] = field(default_factory=dict)


async def run_agent(query: str, *, facility_id: str, user_id: str) -> AgentResponse:
    client = anthropic.AsyncAnthropic()
    ctx = ToolContext(facility_id=facility_id, user_id=user_id)

    messages: list[dict] = [{"role": "user", "content": query}]
    tools_called: list[str] = []
    tool_results_log: list[dict[str, Any]] = []

    for turn in range(MAX_TURNS):
        response = await client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=DEFINITIONS,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            tool_blocks = [b for b in response.content if b.type == "tool_use"]
            results_for_claude = []
            for block in tool_blocks:
                tools_called.append(block.name)
                handler = DISPATCH.get(block.name)
                if handler is None:
                    payload = {"error": f"Unknown tool: {block.name}"}
                else:
                    try:
                        payload = await handler(block.input, ctx)
                    except Exception as exc:
                        log.exception("Tool %s failed", block.name)
                        payload = {"error": "tool_exception", "detail": str(exc)}
                tool_results_log.append({"name": block.name, "input": block.input, "content": payload})
                results_for_claude.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(payload, default=str),
                })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": results_for_claude})
            continue

        # Final response
        final_text = "".join(getattr(b, "text", "") for b in response.content)
        watch_reserve = detect_watch_reserve(final_text, tool_results_log)
        final_text = append_disclaimer(final_text, watch_reserve)
        confidence = confidence_from_tool_results(tool_results_log)

        provenance = Provenance(
            facility_id=facility_id,
            tools_called=tools_called,
            tool_inputs={r["name"]: r["input"] for r in tool_results_log},
            tool_results_summary={r["name"]: _summarize(r["content"]) for r in tool_results_log},
        )

        return AgentResponse(
            recommendation=final_text,
            tools_called=tools_called,
            tool_results=tool_results_log,
            confidence_score=confidence,
            data_provenance=provenance.__dict__,
        )

    # Max turns exhausted
    return AgentResponse(
        recommendation=append_disclaimer(
            "I was unable to complete this analysis within the tool-call budget. "
            "Please try a more specific query, or check the agentic service logs.",
            mentions_watch_reserve=False,
        ),
        tools_called=tools_called,
        tool_results=tool_results_log,
        confidence_score=0.0,
        data_provenance={},
    )


def _summarize(content: Any) -> Any:
    if isinstance(content, dict):
        s = {}
        for k, v in content.items():
            if isinstance(v, list):
                s[k] = f"<list len={len(v)}>"
            elif isinstance(v, dict):
                s[k] = f"<object keys={len(v)}>"
            else:
                s[k] = v
        return s
    return content
