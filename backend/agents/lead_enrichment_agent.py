"""
Lead enrichment — why: turn a raw form row into CRM-ready hints (fit, risks, follow-up).
How: single Bedrock JSON call using only fields we already trust (no transcript required).
"""
from __future__ import annotations

from typing import Any

from .llm import converse_json

SYSTEM = """You are a recruiting CRM assistant.
Return ONLY valid JSON (no markdown fences) with this shape:
{
  "fit_score": number between 0 and 10,
  "fit_rationale": string,
  "risk_flags": [ string ],
  "recommended_follow_up": string,
  "tags": [ string ]
}
Rules:
- Use only the provided fields; do not assume facts not stated.
- risk_flags should be hiring risks or verification needs, not insults.
- tags: short lowercase tokens, max 8.
"""


def run_lead_enrichment(
    *,
    name: str,
    phone: str,
    role: str,
    experience: str,
) -> dict[str, Any]:
    user = (
        f"name: {name}\n"
        f"phone: {phone}\n"
        f"role: {role}\n"
        f"experience: {experience}\n"
    )
    return converse_json(system=SYSTEM, user=user)
