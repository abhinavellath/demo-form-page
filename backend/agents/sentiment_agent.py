"""
Sentiment agent — why: hiring calls are easier to review when tone is summarized.
How: one Bedrock call with a strict JSON schema in the system prompt.
"""
from __future__ import annotations

from typing import Any

from .llm import converse_json

SYSTEM = """You are a sentiment analyst for phone screening interviews.
Return ONLY valid JSON (no markdown fences) with this shape:
{
  "overall_sentiment": "positive" | "neutral" | "negative",
  "overall_confidence": number between 0 and 1,
  "candidate_tone_notes": string,
  "segments": [
    {
      "label": string,
      "sentiment": "positive" | "neutral" | "negative",
      "confidence": number between 0 and 1,
      "evidence": string
    }
  ]
}
Rules:
- Base judgments only on the transcript; do not invent events.
- Keep segments to at most 6 items; merge minor parts.
- "evidence" must be short paraphrases or brief quotes from the transcript.
"""


def run_sentiment(*, transcript: str) -> dict[str, Any]:
    user = f"Transcript:\n{transcript}"
    return converse_json(system=SYSTEM, user=user)
