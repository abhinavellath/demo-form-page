"""
Persist form submissions to Supabase table public.leads.
Failures are logged and swallowed so /lead still completes if DB write fails.
"""
from __future__ import annotations

import json
import os
from typing import Any

import psycopg2
from psycopg2.extras import Json


def _normalize_phone(phone: str) -> str:
    return (phone or "").strip()


def persist_lead(
    *,
    name: str,
    phone: str,
    role: str,
    experience: str,
    rag_meta: dict[str, Any],
    kb_context: str | None,
    lead_ai_enrichment: dict[str, Any] | None,
    vapi_http_status: int,
    vapi_response_text: str | None,
) -> None:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("LEAD_PERSIST: skipped (no DATABASE_URL)")
        return

    vapi_call_id = None
    vapi_call_status = None
    if vapi_response_text:
        try:
            body = json.loads(vapi_response_text)
            if isinstance(body, dict):
                cid = body.get("id")
                vapi_call_id = str(cid) if cid is not None else None
                st = body.get("status")
                vapi_call_status = str(st) if st is not None else None
        except (json.JSONDecodeError, TypeError):
            pass

    phone_n = _normalize_phone(phone)

    try:
        conn = psycopg2.connect(db_url, sslmode="require")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.leads (
                        name, phone, role, experience,
                        rag_meta, kb_context, lead_ai_enrichment,
                        vapi_http_status, vapi_call_id, vapi_call_status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        name,
                        phone_n,
                        role,
                        experience,
                        Json(rag_meta),
                        kb_context,
                        Json(lead_ai_enrichment) if lead_ai_enrichment is not None else None,
                        vapi_http_status,
                        vapi_call_id,
                        vapi_call_status,
                    ),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print("LEAD_PERSIST_FAILED:", repr(e))


def fetch_conversation_memory_for_phone(phone: str) -> str:
    """
    Latest non-null conversation_memory for this phone (JSON string for Vapi variables).
    Returns empty string if none / DB unavailable.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return ""
    phone_n = _normalize_phone(phone)
    try:
        conn = psycopg2.connect(db_url, sslmode="require")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT conversation_memory
                    FROM public.leads
                    WHERE phone = %s AND conversation_memory IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (phone_n,),
                )
                row = cur.fetchone()
        finally:
            conn.close()
    except Exception as e:
        print("FETCH_MEMORY_FAILED:", repr(e))
        return ""

    if not row or row[0] is None:
        return ""
    try:
        return json.dumps(row[0], ensure_ascii=False)
    except (TypeError, ValueError):
        return ""


def find_lead_by_vapi_call_id(vapi_call_id: str) -> dict[str, Any] | None:
    db_url = os.getenv("DATABASE_URL")
    if not db_url or not vapi_call_id:
        return None
    try:
        conn = psycopg2.connect(db_url, sslmode="require")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        name,
                        phone,
                        role,
                        experience,
                        kb_context,
                        conversation_memory,
                        ai_pipeline_status
                    FROM public.leads
                    WHERE vapi_call_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (vapi_call_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()
    except Exception as e:
        print("FIND_LEAD_BY_CALL_FAILED:", repr(e))
        return None

    if not row:
        return None
    return {
        "id": str(row[0]),
        "name": row[1],
        "phone": row[2],
        "role": row[3],
        "experience": row[4],
        "kb_context": row[5],
        "conversation_memory": row[6],
        "ai_pipeline_status": row[7],
    }


def find_lead_by_id(lead_id: str) -> dict[str, Any] | None:
    db_url = os.getenv("DATABASE_URL")
    if not db_url or not lead_id:
        return None
    try:
        conn = psycopg2.connect(db_url, sslmode="require")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        name,
                        phone,
                        role,
                        experience,
                        kb_context,
                        conversation_memory,
                        ai_pipeline_status,
                        vapi_call_id
                    FROM public.leads
                    WHERE id = %s::uuid
                    LIMIT 1
                    """,
                    (lead_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()
    except Exception as e:
        print("FIND_LEAD_BY_ID_FAILED:", repr(e))
        return None

    if not row:
        return None
    return {
        "id": str(row[0]),
        "name": row[1],
        "phone": row[2],
        "role": row[3],
        "experience": row[4],
        "kb_context": row[5],
        "conversation_memory": row[6],
        "ai_pipeline_status": row[7],
        "vapi_call_id": row[8],
    }


def update_lead_post_call_results(
    *,
    lead_id: str,
    transcript: str,
    vapi_summary: str | None,
    sentiment: dict[str, Any] | None,
    qa_evaluation: dict[str, Any] | None,
    conversation_memory: dict[str, Any] | None,
    ai_pipeline_status: str,
    ai_pipeline_error: str | None,
) -> None:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("UPDATE_POST_CALL: skipped (no DATABASE_URL)")
        return
    try:
        conn = psycopg2.connect(db_url, sslmode="require")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE public.leads
                    SET
                        transcript = %s,
                        vapi_summary = %s,
                        sentiment = %s,
                        qa_evaluation = %s,
                        conversation_memory = COALESCE(%s::jsonb, conversation_memory),
                        ai_pipeline_status = %s,
                        ai_pipeline_error = %s
                    WHERE id = %s::uuid
                    """,
                    (
                        transcript,
                        vapi_summary,
                        Json(sentiment) if sentiment is not None else None,
                        Json(qa_evaluation) if qa_evaluation is not None else None,
                        Json(conversation_memory) if conversation_memory is not None else None,
                        ai_pipeline_status,
                        ai_pipeline_error,
                        lead_id,
                    ),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print("UPDATE_POST_CALL_FAILED:", repr(e))
