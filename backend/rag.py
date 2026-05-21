"""
Call-start RAG: embed query, retrieve kb_chunks from Supabase (pgvector), format kb_context for Vapi.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

import psycopg2
from openai import OpenAI
from pgvector.psycopg2 import register_vector

ALLOWED_ROLES = frozenset({"DevOps Engineer", "AI Engineer"})
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
MAX_TOP_K = 5
RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() in ("1", "true", "yes")


def _chunk_to_embedding_text(chunk: dict[str, Any]) -> str:
    good = chunk.get("good_signals") or []
    bad = chunk.get("bad_signals") or []
    follow = chunk.get("follow_ups") or []
    return "\n".join(
        [
            f"Role: {chunk.get('role', '')}",
            f"Topic: {chunk.get('topic', '')}",
            f"Question: {chunk.get('question', '')}",
            f"Purpose: {chunk.get('why_this_is_asked', '')}",
            "Good signals: " + "; ".join(str(x) for x in good),
            "Bad signals: " + "; ".join(str(x) for x in bad),
            "Follow-ups: " + "; ".join(str(x) for x in follow),
        ]
    )


def _format_kb_context(rows: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for i, row in enumerate(rows, start=1):
        topic = row.get("topic") or "General"
        cj = row.get("chunk_json")
        if isinstance(cj, dict):
            q = cj.get("question", "")
            purpose = cj.get("why_this_is_asked", "")
            follow = cj.get("follow_ups") or []
            good = cj.get("good_signals") or []
            bad = cj.get("bad_signals") or []
        else:
            q = purpose = ""
            follow = good = bad = []
        blocks.append(
            "\n".join(
                [
                    f"--- Screening block {i} ({topic}) ---",
                    f"Question: {q}",
                    f"Purpose: {purpose}",
                    "Good signals: " + "; ".join(str(x) for x in good),
                    "Bad signals: " + "; ".join(str(x) for x in bad),
                    "Suggested follow-ups: " + "; ".join(str(x) for x in follow),
                ]
            )
        )
    return "\n\n".join(blocks)


def _fallback_context(reason: str) -> str:
    return (
        "No structured question bank was retrieved for this call. "
        f"({reason}) "
        "Use the general screening topics from your instructions and candidate details only."
    )


def _build_query(role: str, experience: str, name: str) -> str:
    return (
        f"Role: {role}. "
        f"Years of experience (self-reported): {experience}. "
        f"Candidate name (for context only): {name}. "
        "Task: retrieve the official phone-screen question bank for this role. "
        "Prioritize practical depth over theory."
    )


def retrieve_kb_context(
    role: str,
    experience: str,
    name: str,
) -> tuple[str, dict[str, Any]]:
    """
    Returns (kb_context_string, metadata_for_logs).
    Never raises — failures return a safe fallback string.
    """
    meta: dict[str, Any] = {
        "rag_enabled": RAG_ENABLED,
        "role": role,
        "latency_ms": None,
        "chunk_topics": [],
        "distances": [],
        "chunks_used": 0,
        "error": None,
    }
    t0 = time.perf_counter()

    if not RAG_ENABLED:
        meta["error"] = "rag_disabled"
        meta["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        return _fallback_context("RAG disabled via RAG_ENABLED"), meta

    if role not in ALLOWED_ROLES:
        meta["error"] = "role_not_in_kb"
        meta["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        return _fallback_context(f"Role '{role}' is not in the knowledge base"), meta

    db_url = os.getenv("DATABASE_URL")
    api_key = os.getenv("OPENAI_API_KEY")
    if not db_url or not api_key:
        meta["error"] = "missing_env"
        meta["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        return _fallback_context("Missing DATABASE_URL or OPENAI_API_KEY"), meta

    query_text = _build_query(role, experience, name)

    try:
        client = OpenAI(api_key=api_key)
        emb_resp = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=query_text,
        )
        query_vec = emb_resp.data[0].embedding
    except Exception as e:
        meta["error"] = f"embed_failed:{e}"
        meta["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        return _fallback_context("Embedding request failed"), meta

    conn = None
    try:
        conn = psycopg2.connect(db_url, sslmode="require")
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM kb_chunks WHERE role = %s",
                (role,),
            )
            (n_chunks,) = cur.fetchone()
            n_chunks = int(n_chunks or 0)
            top_k = min(MAX_TOP_K, n_chunks)

            meta["chunks_available"] = n_chunks
            meta["top_k"] = top_k

            if top_k == 0:
                meta["error"] = "no_rows_for_role"
                meta["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
                return _fallback_context(f"No KB rows stored for role '{role}'"), meta

            cur.execute(
                """
                SELECT topic, chunk_json, (embedding <=> %s::vector) AS dist
                FROM kb_chunks
                WHERE role = %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (query_vec, role, query_vec, top_k),
            )
            fetched = cur.fetchall()
    except Exception as e:
        meta["error"] = f"db_failed:{e}"
        meta["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        return _fallback_context("Database retrieval failed"), meta
    finally:
        if conn is not None:
            conn.close()

    rows: list[dict[str, Any]] = []
    for topic, chunk_json, dist in fetched:
        cj = chunk_json if isinstance(chunk_json, dict) else {}
        rows.append({"topic": topic, "chunk_json": cj})
        meta["chunk_topics"].append(topic)
        meta["distances"].append(float(dist) if dist is not None else None)

    meta["chunks_used"] = len(rows)
    meta["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    ctx = _format_kb_context(rows)
    return ctx, meta
