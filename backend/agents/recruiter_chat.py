"""
In-browser / text demo: recruiter dialogue using the same KB context as Vapi,
via Bedrock multi-turn chat (plain text, not JSON agents).
"""
from __future__ import annotations

import os
from typing import Any

from .llm import converse_text, get_default_chat_model_id

# OOC user line used only to bootstrap the model; omitted from post-call transcript.
DEMO_CHAT_CONNECT_USER_MESSAGE = (
    "(OOC: The candidate just joined the text screening chat. "
    "Respond only with your opening recruiter message: brief intro, confirm who you're speaking with, "
    "and one short sentence on why you're here. Do not ask a screening question yet.)"
)


def _build_system_prompt(
    *,
    candidate_name: str,
    role: str,
    experience: str,
    kb_context: str | None,
    prior_memory_json: str | None,
) -> str:
    kb = (kb_context or "").strip() or "No structured question bank was retrieved; use general topics."
    mem = (prior_memory_json or "").strip()
    mem_block = (
        f"\n\nPrior conversation memory (JSON, may be empty):\n{mem}\n"
        if mem and mem != "{}"
        else ""
    )
    return f"""You are an AI recruiter assistant conducting initial screening via **text chat** (not a phone call).

Personality: professional, friendly, conversational, confident, concise.

Candidate:
- Name: {candidate_name}
- Role applied: {role}
- Experience: {experience}
{mem_block}

## Authoritative question bank (retrieval)

Treat the following as the **primary source** for which technical screening questions to ask.

{kb}

If the block clearly states that no structured bank was retrieved, use the general topics below instead of inventing a parallel bank.

## Objectives

1. Sound natural in short chat messages (2–5 sentences max per reply unless the candidate writes a lot).
2. When a question bank is present: ask those questions **in order**, **one main question at a time**; use suggested follow-ups only when an answer is vague.
3. If using fallback topics: cover them one at a time: current role, years of experience, Python, AI/ML, AWS/Kubernetes, notice period, salary expectations, interest in moving.
4. Never sound robotic; no long monologues; do not stack multiple unrelated questions in one message.
5. Do not invent a second questionnaire when the retrieved bank is present.

## Closing

If the candidate seems qualified, end positively and say the team will follow up.
If they are not interested, thank them politely.
"""


def run_recruiter_opening(
    *,
    candidate_name: str,
    role: str,
    experience: str,
    kb_context: str | None,
    prior_memory_json: str | None,
) -> str:
    if not get_default_chat_model_id():
        return (
            f"Hi {candidate_name}, This is Sarah from TalentBridge Recruiting. "
            f"I'll ask a few questions about your background for the {role} role. "
            "Whenever you're ready, reply with a short message and we'll get started."
        )
    system = _build_system_prompt(
        candidate_name=candidate_name,
        role=role,
        experience=experience,
        kb_context=kb_context,
        prior_memory_json=prior_memory_json,
    )
    temp = float(os.getenv("RECRUITER_CHAT_TEMPERATURE", "0.35"))
    return converse_text(
        system=system,
        messages=[{"role": "user", "content": DEMO_CHAT_CONNECT_USER_MESSAGE}],
        temperature=temp,
    )


def run_recruiter_turn(
    *,
    transcript_turns: list[tuple[str, str]],
    user_message: str,
    candidate_name: str,
    role: str,
    experience: str,
    kb_context: str | None,
    prior_memory_json: str | None,
) -> str:
    """Append user_message as the latest user turn; returns assistant reply text."""
    if not get_default_chat_model_id():
        return (
            "Thanks for your message. (Demo: configure Bedrock / BEDROCK_CHAT_MODEL_ID for live AI replies.)"
        )
    system = _build_system_prompt(
        candidate_name=candidate_name,
        role=role,
        experience=experience,
        kb_context=kb_context,
        prior_memory_json=prior_memory_json,
    )
    messages: list[dict[str, Any]] = []
    for r, c in transcript_turns:
        if r in ("user", "assistant"):
            messages.append({"role": r, "content": c})
    messages.append({"role": "user", "content": user_message.strip()})

    temp = float(os.getenv("RECRUITER_CHAT_TEMPERATURE", "0.35"))
    return converse_text(system=system, messages=messages, temperature=temp)


def format_transcript_for_post_call(turns: list[tuple[str, str]]) -> str:
    """Human-readable transcript for sentiment/QA/memory agents."""
    lines: list[str] = []
    for role, content in turns:
        if role == "user" and content.strip() == DEMO_CHAT_CONNECT_USER_MESSAGE.strip():
            continue
        label = "Candidate" if role == "user" else "AI Recruiter"
        lines.append(f"{label}: {content.strip()}")
    return "\n".join(lines).strip()
