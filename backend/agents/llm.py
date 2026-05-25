"""
Minimal Bedrock Converse helper for JSON-only agent outputs.

Deferred “Phase 3” polish: this file is the single place that talks to
`bedrock-runtime` for chat. Agents call `converse_json` only.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

# Haiku 4.5: many accounts cannot use the foundation model id with on-demand Converse — use a
# geo inference profile (see AWS model card "Geo inference ID"). Override anytime with BEDROCK_CHAT_MODEL_ID.
# Also enable model access + Anthropic use case in the Bedrock console.
_HAIKU_45 = "claude-haiku-4-5-20251001-v1:0"


def _default_haiku_45_inference_profile(region: str) -> str:
    r = (region or "us-east-1").strip().lower()
    if r.startswith("eu-"):
        return f"eu.anthropic.{_HAIKU_45}"
    if r.startswith("ap-northeast-"):
        return f"jp.anthropic.{_HAIKU_45}"
    if r in ("ap-southeast-2", "ap-southeast-4", "ap-southeast-6"):
        return f"au.anthropic.{_HAIKU_45}"
    # us-east-1, us-west-*, ca-*, etc. → US geo profile (per AWS Haiku 4.5 routing table)
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


def converse_json(*, system: str, user: str, model_id: str | None = None) -> dict[str, Any]:
    """
    One Converse round-trip; model must return a single JSON object as text.
    """
    mid = (model_id or get_default_chat_model_id()).strip()
    if not mid:
        raise RuntimeError("Chat model id is empty (set BEDROCK_CHAT_MODEL_ID or AWS_REGION)")

    client = _bedrock_runtime()
    resp = client.converse(
        modelId=mid,
        system=[{"text": system}],
        messages=[{"role": "user", "content": [{"text": user}]}],
        inferenceConfig={
            "maxTokens": int(os.getenv("BEDROCK_CHAT_MAX_TOKENS", "4096")),
            "temperature": float(os.getenv("BEDROCK_CHAT_TEMPERATURE", "0.2")),
        },
    )

    out = resp.get("output", {}).get("message", {})
    parts = out.get("content") or []
    texts: list[str] = []
    for p in parts:
        if isinstance(p, dict) and "text" in p:
            texts.append(str(p["text"]))
    raw = "\n".join(texts).strip()
    if not raw:
        raise RuntimeError("Empty model text output")

    cleaned = _strip_json_fences(raw)
    return json.loads(cleaned)
