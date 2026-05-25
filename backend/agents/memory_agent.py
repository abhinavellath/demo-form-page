"""
Conversation memory agent — why: next call can start with continuity (Phase 7).
How: summarize transcript + merge with prior memory JSON if present.
"""
from __future__ import annotations

import json
from typing import Any

from .llm import converse_json

SYSTEM = """You are a conversation memory writer for recruiting calls.
Return ONLY valid JSON (no markdown fences) with this shape:
{
  "summary": string,
  "facts_for_next_call": [ string ],
  "open_questions": [ string ],
  "do_not_repeat": [ string ]
}
Rules:
- facts_for_next_call must be short, factual bullets grounded in the transcript.
- If prior_memory_json is provided, merge: keep still-true facts, drop contradictions, add new facts.
- do_not_repeat: things the assistant should avoid repeating next time (e.g. already confirmed logistics).
- No invented phone numbers, employers, or credentials.
"""


def run_memory(
    *,
    transcript: str,
    prior_memory: dict[str, Any] | None,
    candidate_name: str,
    role: str,
) -> dict[str, Any]:
    prior = json.dumps(prior_memory, ensure_ascii=False) if prior_memory else "(none)"
    user = (
        f"candidate_name: {candidate_name}\n"
        f"role: {role}\n"
        f"prior_memory_json: {prior}\n\n"
        f"transcript:\n{transcript}"
    )
    return converse_json(system=SYSTEM, user=user)
