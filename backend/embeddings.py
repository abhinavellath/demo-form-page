"""
AWS Bedrock — Amazon Titan Text Embeddings v1 (1536 dimensions).
Used for RAG ingest + query-time retrieval (matches pgvector vector(1536)).
"""
from __future__ import annotations

import json
import os
from typing import Any

# Must match Supabase kb_chunks.embedding column (see supabase/sql/001_kb_chunks.sql).
BEDROCK_TITAN_V1_DIM = 1536
DEFAULT_MODEL_ID = "amazon.titan-embed-text-v1"


def _bedrock_client():
    import boto3

    region = os.getenv("AWS_REGION", "us-east-1")
    return boto3.client("bedrock-runtime", region_name=region)


def embed_titan_v1(text: str) -> list[float]:
    """Single text → 1536-dim embedding via Titan Embeddings v1."""
    model_id = os.getenv("BEDROCK_EMBEDDING_MODEL_ID", DEFAULT_MODEL_ID)
    client = _bedrock_client()
    body = json.dumps({"inputText": text})
    resp = client.invoke_model(
        modelId=model_id,
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    payload: dict[str, Any] = json.loads(resp["body"].read())
    vec = payload.get("embedding")
    if not isinstance(vec, list) or len(vec) != BEDROCK_TITAN_V1_DIM:
        raise ValueError(
            f"Unexpected Titan embedding length: {len(vec) if isinstance(vec, list) else 'n/a'}, expected {BEDROCK_TITAN_V1_DIM}"
        )
    return [float(x) for x in vec]


def embed_titan_v1_batch(texts: list[str]) -> list[list[float]]:
    """
    Titan v1 accepts one inputText per request — call in sequence.
    (Fine for small KB ingest; batch size is typically ≤20 chunks.)
    """
    return [embed_titan_v1(t) for t in texts]
