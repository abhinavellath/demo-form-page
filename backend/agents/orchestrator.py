"""
Post-call agentic core — why: one entrypoint so webhook + debug path stay consistent.
How: sentiment + QA in parallel threads (I/O bound Bedrock calls), then memory sequentially.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from .llm import get_default_chat_model_id
from .lead_enrichment_agent import run_lead_enrichment
from .memory_agent import run_memory
from .qa_eval_agent import run_qa_eval
from .sentiment_agent import run_sentiment


def run_lead_enrichment_safe(
    *, name: str, phone: str, role: str, experience: str
) -> dict[str, Any] | None:
    if not get_default_chat_model_id():
        return None
    try:
        return run_lead_enrichment(
            name=name, phone=phone, role=role, experience=experience
        )
    except Exception as e:
        return {"error": repr(e)}


def run_post_call_pipeline(
    *,
    transcript: str,
    kb_context: str | None,
    candidate_name: str,
    role: str,
    prior_memory: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Returns keys: sentiment, qa_evaluation, conversation_memory, errors (list).
    Individual agent failures are captured; memory still runs if possible.
    """
    if not get_default_chat_model_id():
        return {
            "sentiment": None,
            "qa_evaluation": None,
            "conversation_memory": None,
            "errors": ["bedrock_chat_model_missing"],
        }

    errors: list[str] = []
    sentiment: dict[str, Any] | None = None
    qa_evaluation: dict[str, Any] | None = None

    def _sentiment() -> dict[str, Any]:
        return run_sentiment(transcript=transcript)

    def _qa() -> dict[str, Any]:
        return run_qa_eval(transcript=transcript, kb_context=kb_context)

    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = {
            ex.submit(_sentiment): "sentiment",
            ex.submit(_qa): "qa",
        }
        for fut in as_completed(futs):
            label = futs[fut]
            try:
                result = fut.result()
                if label == "sentiment":
                    sentiment = result
                else:
                    qa_evaluation = result
            except Exception as e:
                errors.append(f"{label}:{repr(e)}")

    conversation_memory: dict[str, Any] | None = None
    try:
        conversation_memory = run_memory(
            transcript=transcript,
            prior_memory=prior_memory,
            candidate_name=candidate_name,
            role=role,
        )
    except Exception as e:
        errors.append(f"memory:{repr(e)}")

    return {
        "sentiment": sentiment,
        "qa_evaluation": qa_evaluation,
        "conversation_memory": conversation_memory,
        "errors": errors,
    }
