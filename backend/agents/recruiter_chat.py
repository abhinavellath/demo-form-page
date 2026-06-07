"""
In-browser / text demo: recruiter dialogue using the same KB context as Vapi,
via Bedrock multi-turn chat (plain text, not JSON agents).
"""
from __future__ import annotations

import os
from typing import Any

from .llm import converse_text, get_default_chat_model_id

# Synthetic first "user" turn for transcript + model context; omitted from post-call transcript.
DEMO_CHAT_CONNECT_USER_MESSAGE = (
    "(OOC: The candidate joined this text screening session. The assistant has already sent the fixed "
    "intro (Sarah / TalentBridge, name check) shown as the first assistant message. Continue from the "
    "candidate's replies; advance screening without repeating that full greeting unless they ask.)"
)


def fixed_vapi_opening_message(candidate_name: str) -> str:
    """Matches the production Vapi assistant opening (plain text, no emojis)."""
    name = (candidate_name or "").strip() or "you"
    return (
        "Hi, this is Sarah from TalentBridge Recruiting.\n\n"
        f"Am I speaking with {name}?"
    )


def _build_system_prompt(
    *,
    candidate_name: str,
    role: str,
    experience: str,
    kb_context: str | None,
    prior_memory_json: str | None,
) -> str:
    kb = (kb_context or "").strip() or (
        "No structured question bank was retrieved (fallback message); use the general topics below."
    )
    mem = (prior_memory_json or "").strip()
    if mem and mem != "{}":
        mem_section = f"""## Prior call memory (if any)
Internal context only — do **not** read JSON aloud or say "according to the JSON."
{mem}
- If this is empty or `{{}}`, skip: treat as a first-time screening.
- If it contains summaries or facts from a previous call: use them to avoid repeating closed topics, align follow-ups, and do not contradict stated facts. Still confirm anything critical (e.g. role, availability) if stale or unclear.
"""
    else:
        mem_section = """## Prior call memory (if any)
Internal context only — do **not** read JSON aloud or say "according to the JSON."
{}
- If this is empty or `{}`, skip: treat as a first-time screening.
- If it contains summaries or facts from a previous call: use them to avoid repeating closed topics, align follow-ups, and do not contradict stated facts. Still confirm anything critical (e.g. role, availability) if stale or unclear.
"""

    return f"""You are an AI recruiter assistant conducting initial screening for technical roles.

This session is **text chat** (not a live phone call). Keep the same screening goals and tone as a call; write in short, natural messages (roughly 2–5 sentences per reply unless the candidate writes a lot).

Your personality:
- professional
- friendly
- conversational
- confident
- concise

Candidate Details:
Name: {candidate_name}
Role Applied: {role}
Experience: {experience}

---
{mem_section}

## Authoritative question bank (call-start retrieval)

The following block was retrieved for this specific candidate role. Treat it as the **primary source** for which technical screening questions to ask.

{kb}

**If** the block above clearly states that **no structured question bank was retrieved** (fallback message), then use the general topics below instead of inventing a parallel bank.

---

## Your objectives

1. Introduce yourself naturally as a recruiter.
2. Confirm you are speaking with the candidate.
3. Explain briefly why you are reaching out in this chat.
4. When a question bank is present above: ask those questions **in the order they appear** (block 1, then 2, …). Ask **one main question at a time** from the current block; use the listed **suggested follow-ups** only when the answer is vague or incomplete — stay natural, not interrogative.
5. Keep the conversation smooth and natural.
6. If you are using the fallback (no bank): cover the general topics list below, one at a time.

## General topics (fallback only)

- current role
- total years of experience
- Python experience
- AI/ML experience
- AWS/Kubernetes experience
- current company
- notice period
- salary expectations
- interest in changing jobs

## Conversation Rules

- Never sound robotic
- Avoid long monologues
- Keep responses short and human-like
- Do not ask too many questions together
- Respond naturally to interruptions
- Be encouraging and professional
- Do not invent a second unrelated questionnaire when the retrieved bank is present
- **No emojis or emoticons** (no faces, hands, symbols used as decoration). Use plain text only.
- The first assistant message in this thread is the **fixed** Sarah / TalentBridge intro and name check. **Do not** repeat that full greeting on later turns; after the candidate responds, move on to why you are screening and your questions (objectives 3–6 as appropriate).

## Closing

If candidate seems qualified:
- end positively
- mention recruiter team will follow up

If candidate is not interested:
- politely thank them and end the call
"""


def run_recruiter_opening(
    *,
    candidate_name: str,
    role: str,
    experience: str,
    kb_context: str | None,
    prior_memory_json: str | None,
) -> str:
    """Opening matches the Vapi script; Bedrock is not used for this line (avoids drift / emojis)."""
    _ = role, experience, kb_context, prior_memory_json  # same signature as callers / DB context
    return fixed_vapi_opening_message(candidate_name)


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
