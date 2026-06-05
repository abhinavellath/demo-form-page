"""
Bedrock chat for agent JSON outputs via invoke_model (Anthropic Messages API on Bedrock).

Uses boto3 bedrock-runtime.invoke_model — same IAM model access as the console "enabled"
Anthropic models; does not use the Converse API.

Agents still call converse_json(); name is legacy.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

# Haiku 4.5: many accounts need the geo inference profile, not the bare foundation model id.
# Override anytime with BEDROCK_CHAT_MODEL_ID.
_HAIKU_45 = "claude-haiku-4-5-20251001-v1:0"


def _default_haiku_45_inference_profile(region: str) -> str:
    r = (region or "us-east-1").strip().lower()
    if r.startswith("eu-"):
        return f"eu.anthropic.{_HAIKU_45}"
    if r.startswith("ap-northeast-"):
        return f"jp.anthropic.{_HAIKU_45}"
    if r in ("ap-southeast-2", "ap-southeast-4", "ap-southeast-6"):
        return f"au.anthropic.{_HAIKU_45}"
    return f"us.anthropic.{_HAIKU_45}"


def get_default_chat_model_id() -> str:
    explicit = os.getenv("BEDROCK_CHAT_MODEL_ID", "").strip()
    if explicit:
        return explicit
    return _default_haiku_45_inference_profile(os.getenv("AWS_REGION", "us-east-1"))


def _bedrock_runtime():
    import boto3

    region = os.getenv("AWS_REGION", "us-east-1")
    return boto3.client("bedrock-runtime", region_name=region)


def _strip_json_fences(text: str) -> str:
    t = text.strip()
    m = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", t, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return t


def _extract_text_from_anthropic_response(payload: dict[str, Any]) -> str:
    """Bedrock invoke_model body for Anthropic Claude 3+ messages format."""
    parts: list[str] = []
    for block in payload.get("content") or []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and "text" in block:
            parts.append(str(block["text"]))
    return "\n".join(parts).strip()


def converse_json(*, system: str, user: str, model_id: str | None = None) -> dict[str, Any]:
    """
    One round-trip via invoke_model; model must return a single JSON object as text.

    Request shape matches Anthropic on Bedrock (Messages API):
    https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages.html
    """
    mid = (model_id or get_default_chat_model_id()).strip()
    if not mid:
        raise RuntimeError("Chat model id is empty (set BEDROCK_CHAT_MODEL_ID or AWS_REGION)")

    anthropic_version = os.getenv("BEDROCK_ANTHROPIC_VERSION", "bedrock-2023-05-31").strip()
    max_tokens = int(os.getenv("BEDROCK_CHAT_MAX_TOKENS", "4096"))
    temperature = float(os.getenv("BEDROCK_CHAT_TEMPERATURE", "0.2"))

    body: dict[str, Any] = {
        "anthropic_version": anthropic_version,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }

    client = _bedrock_runtime()
    resp = client.invoke_model(
        modelId=mid,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )

    raw_bytes = resp.get("body")
    if raw_bytes is None:
        raise RuntimeError("Empty invoke_model response body")
    payload: dict[str, Any] = json.loads(raw_bytes.read())

    raw = _extract_text_from_anthropic_response(payload)
    if not raw:
        raise RuntimeError("Empty model text output")

    cleaned = _strip_json_fences(raw)
    return json.loads(cleaned)


def converse_text(
    *,
    system: str,
    messages: list[dict[str, Any]],
    model_id: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    """
    Multi-turn Bedrock invoke; returns plain assistant text (not JSON).
    `messages` items: {"role": "user"|"assistant", "content": str}.
    """
    mid = (model_id or get_default_chat_model_id()).strip()
    if not mid:
        raise RuntimeError("Chat model id is empty (set BEDROCK_CHAT_MODEL_ID or AWS_REGION)")

    anthropic_version = os.getenv("BEDROCK_ANTHROPIC_VERSION", "bedrock-2023-05-31").strip()
    mt = max_tokens if max_tokens is not None else int(os.getenv("BEDROCK_CHAT_MAX_TOKENS", "4096"))
    temp = (
        temperature
        if temperature is not None
        else float(os.getenv("BEDROCK_CHAT_TEMPERATURE", "0.2"))
    )

    body: dict[str, Any] = {
        "anthropic_version": anthropic_version,
        "max_tokens": mt,
        "temperature": temp,
        "system": system,
        "messages": messages,
    }

    client = _bedrock_runtime()
    resp = client.invoke_model(
        modelId=mid,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )

    raw_bytes = resp.get("body")
    if raw_bytes is None:
        raise RuntimeError("Empty invoke_model response body")
    payload: dict[str, Any] = json.loads(raw_bytes.read())

    raw = _extract_text_from_anthropic_response(payload)
    if not raw:
        raise RuntimeError("Empty model text output")
    return raw.strip()
