"""
QA evaluation agent — why: score answers against the same rubric the assistant had (kb_context).
How: pass the stored kb_context string + transcript; model returns structured scores.
"""
from __future__ import annotations

from typing import Any

from .llm import converse_json

SYSTEM = """You are an interview evaluator.
You will receive:
1) The official screening rubric / question bank text used on the call (kb_context).
2) The call transcript.

Return ONLY valid JSON (no markdown fences) with this shape:
{
  "overall_score": number between 0 and 10,
  "overall_rationale": string,
  "themes": [
    {
      "theme": string,
      "score": number between 0 and 10,
      "what_went_well": string,
      "gaps_or_risks": string,
      "evidence_quotes": [ string ]
    }
  ]
}
Rules:
- Score against kb_context themes and signals; if kb_context is empty, infer themes from transcript only and say so in overall_rationale.
- evidence_quotes must be short excerpts from the transcript (or empty if none).
- At most 8 themes.
"""


def run_qa_eval(*, transcript: str, kb_context: str | None) -> dict[str, Any]:
    kb = (kb_context or "").strip() or "(no kb_context was provided)"
    user = "=== kb_context (rubric) ===\n" + kb + "\n\n=== transcript ===\n" + transcript
    return converse_json(system=SYSTEM, user=user)
