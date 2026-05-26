"""Claude-as-judge eval harness.

Runs a panel of clinical queries through the agentic service and asks Claude
to score the response on four dimensions: clinical appropriateness, guideline
alignment, use of local data, and explanation quality.

This is a quality gate — a new ML model or agent prompt is not deployed unless
it passes a minimum score on this panel.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

import httpx

log = logging.getLogger(__name__)


JUDGE_SYSTEM = """You are evaluating clinical decision-support recommendations from
an AMR stewardship system. Score each recommendation 1-5 on these dimensions:

1. Clinical appropriateness — does it match accepted clinical practice?
2. Guideline alignment — does it cite or align with WHO/IDSA guidelines?
3. Use of local data — does it ground in the facility's own resistance data?
4. Explanation quality — is the reasoning clear and actionable?

Respond with JSON only:
{"appropriateness": int, "guidelines": int, "local_data": int, "explanation": int, "comments": str}
"""


@dataclass
class EvalCase:
    name: str
    facility_id: str
    query: str
    expected_themes: list[str]


@dataclass
class EvalResult:
    case: EvalCase
    response: str
    scores: dict[str, int]
    comments: str
    pass_threshold: bool


DEFAULT_PANEL: list[EvalCase] = [
    EvalCase(
        name="empiric_uti_adult",
        facility_id="FACILITY_001",
        query="A 35-year-old woman presents with uncomplicated UTI. What empiric therapy do you recommend?",
        expected_themes=["nitrofurantoin", "fosfomycin", "trimethoprim"],
    ),
    EvalCase(
        name="empiric_bsi_icu",
        facility_id="FACILITY_001",
        query="An ICU patient has a suspected gram-negative bloodstream infection. What should we start?",
        expected_themes=["broad-spectrum", "antibiogram", "carbapenem"],
    ),
    EvalCase(
        name="deescalation_pip_tazo",
        facility_id="FACILITY_001",
        query="Patient on piperacillin-tazobactam for 48h. Cultures show E. coli susceptible to ampicillin. Can we de-escalate?",
        expected_themes=["de-escalate", "ampicillin", "narrow"],
    ),
]


def run_panel(panel: Optional[list[EvalCase]] = None,
              agentic_url: Optional[str] = None,
              pass_threshold: int = 4) -> list[EvalResult]:
    panel = panel or DEFAULT_PANEL
    base = agentic_url or os.getenv("AGENTIC_SERVICE_URL", "http://localhost:8003")

    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic SDK not installed")

    client = anthropic.Anthropic()
    results: list[EvalResult] = []

    for case in panel:
        try:
            r = httpx.post(f"{base}/query",
                           headers={"X-Facility-Id": case.facility_id, "X-User-Id": "eval-harness"},
                           json={"query": case.query}, timeout=120)
            r.raise_for_status()
            agent_response = r.json().get("recommendation", "")
        except Exception as exc:
            log.error("Agent call failed for %s: %s", case.name, exc)
            results.append(EvalResult(
                case=case, response="", scores={"error": 0},
                comments=str(exc), pass_threshold=False,
            ))
            continue

        judge = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=JUDGE_SYSTEM,
            messages=[{
                "role": "user",
                "content": f"Query: {case.query}\n\nResponse:\n{agent_response}\n\nReturn JSON only.",
            }],
        )
        text = "".join(b.text for b in judge.content if hasattr(b, "text"))
        try:
            scores = json.loads(text)
            comments = scores.pop("comments", "")
        except json.JSONDecodeError:
            scores = {"appropriateness": 0, "guidelines": 0, "local_data": 0, "explanation": 0}
            comments = f"Judge returned invalid JSON: {text[:200]}"

        passed = all(int(scores.get(k, 0)) >= pass_threshold
                     for k in ("appropriateness", "guidelines", "local_data", "explanation"))
        results.append(EvalResult(case=case, response=agent_response, scores=scores,
                                  comments=str(comments), pass_threshold=passed))

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = run_panel()
    n_pass = sum(1 for r in results if r.pass_threshold)
    print(f"Eval: {n_pass}/{len(results)} cases passed")
    for r in results:
        print(f"  - {r.case.name}: scores={r.scores} pass={r.pass_threshold}")
