"""
Persistence: public.leads (CRM), public.chats (per call / transcript + summary),
public.chat_ai_metadata (1:1 RAG + Bedrock outputs per chat).
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
                    INSERT INTO public.leads (name, phone, role, experience)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (name, phone_n, role, experience),
                )
                (lead_id,) = cur.fetchone()

                cur.execute(
                    """
                    INSERT INTO public.chats (
                        lead_id, vapi_call_id, vapi_create_http_status,
                        vapi_call_status, kb_context
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (lead_id, vapi_call_id, vapi_http_status, vapi_call_status, kb_context),
                )
                (chat_id,) = cur.fetchone()

                cur.execute(
                    """
                    INSERT INTO public.chat_ai_metadata (
                        chat_id, rag_meta, lead_ai_enrichment
                    )
                    VALUES (%s, %s, %s)
                    """,
                    (
                        chat_id,
                        Json(rag_meta),
                        Json(lead_ai_enrichment)
                        if lead_ai_enrichment is not None
                        else None,
                    ),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print("LEAD_PERSIST_FAILED:", repr(e))


def fetch_conversation_memory_for_phone(phone: str) -> str:
    """
    Latest non-null conversation_memory from any prior chat for this phone
    (JSON string for Vapi variables).
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
                    SELECT m.conversation_memory
                    FROM public.chat_ai_metadata m
                    JOIN public.chats c ON c.id = m.chat_id
                    JOIN public.leads l ON l.id = c.lead_id
                    WHERE l.phone = %s AND m.conversation_memory IS NOT NULL
                    ORDER BY c.created_at DESC
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


def fetch_prior_conversation_memory_for_phone(
    phone: str, exclude_chat_id: str
) -> dict[str, Any] | None:
    """Memory from the most recent other chat for this phone (excludes current call)."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return None
    phone_n = _normalize_phone(phone)
    try:
        conn = psycopg2.connect(db_url, sslmode="require")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT m.conversation_memory
                    FROM public.chat_ai_metadata m
                    JOIN public.chats c ON c.id = m.chat_id
                    JOIN public.leads l ON l.id = c.lead_id
                    WHERE l.phone = %s
                      AND c.id <> %s::uuid
                      AND m.conversation_memory IS NOT NULL
                    ORDER BY c.created_at DESC
                    LIMIT 1
                    """,
                    (phone_n, exclude_chat_id),
                )
                row = cur.fetchone()
        finally:
            conn.close()
    except Exception as e:
        print("FETCH_PRIOR_MEMORY_FAILED:", repr(e))
        return None

    if not row or row[0] is None:
        return None
    mem = row[0]
    return mem if isinstance(mem, dict) else None


def find_post_call_context_by_vapi_call_id(vapi_call_id: str) -> dict[str, Any] | None:
    """Resolve chat + lead for webhook (by Vapi call id)."""
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
                        l.id,
                        l.name,
                        l.phone,
                        l.role,
                        l.experience,
                        c.id,
                        c.kb_context,
                        m.ai_pipeline_status,
                        m.conversation_memory
                    FROM public.chats c
                    JOIN public.leads l ON l.id = c.lead_id
                    LEFT JOIN public.chat_ai_metadata m ON m.chat_id = c.id
                    WHERE c.vapi_call_id = %s
                    ORDER BY c.created_at DESC
                    LIMIT 1
                    """,
                    (vapi_call_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()
    except Exception as e:
        print("FIND_CHAT_BY_CALL_FAILED:", repr(e))
        return None

    if not row:
        return None
    return {
        "lead_id": str(row[0]),
        "name": row[1],
        "phone": row[2],
        "role": row[3],
        "experience": row[4],
        "chat_id": str(row[5]),
        "kb_context": row[6],
        "ai_pipeline_status": row[7],
        "conversation_memory": row[8],
    }


def find_post_call_context_by_lead_id(lead_id: str) -> dict[str, Any] | None:
    """Latest chat for a lead (replay by lead_id)."""
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
                        l.id,
                        l.name,
                        l.phone,
                        l.role,
                        l.experience,
                        c.id,
                        c.kb_context,
                        m.ai_pipeline_status,
                        m.conversation_memory
                    FROM public.leads l
                    JOIN public.chats c ON c.lead_id = l.id
                    LEFT JOIN public.chat_ai_metadata m ON m.chat_id = c.id
                    WHERE l.id = %s::uuid
                    ORDER BY c.created_at DESC
                    LIMIT 1
                    """,
                    (lead_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()
    except Exception as e:
        print("FIND_CHAT_BY_LEAD_FAILED:", repr(e))
        return None

    if not row:
        return None
    return {
        "lead_id": str(row[0]),
        "name": row[1],
        "phone": row[2],
        "role": row[3],
        "experience": row[4],
        "chat_id": str(row[5]),
        "kb_context": row[6],
        "ai_pipeline_status": row[7],
        "conversation_memory": row[8],
    }


def find_post_call_context_by_chat_id(chat_id: str) -> dict[str, Any] | None:
    db_url = os.getenv("DATABASE_URL")
    if not db_url or not chat_id:
        return None
    try:
        conn = psycopg2.connect(db_url, sslmode="require")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        l.id,
                        l.name,
                        l.phone,
                        l.role,
                        l.experience,
                        c.id,
                        c.kb_context,
                        m.ai_pipeline_status,
                        m.conversation_memory
                    FROM public.chats c
                    JOIN public.leads l ON l.id = c.lead_id
                    LEFT JOIN public.chat_ai_metadata m ON m.chat_id = c.id
                    WHERE c.id = %s::uuid
                    LIMIT 1
                    """,
                    (chat_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()
    except Exception as e:
        print("FIND_CHAT_BY_ID_FAILED:", repr(e))
        return None

    if not row:
        return None
    return {
        "lead_id": str(row[0]),
        "name": row[1],
        "phone": row[2],
        "role": row[3],
        "experience": row[4],
        "chat_id": str(row[5]),
        "kb_context": row[6],
        "ai_pipeline_status": row[7],
        "conversation_memory": row[8],
    }


def update_chat_post_call_results(
    *,
    chat_id: str,
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
                    UPDATE public.chats
                    SET
                        transcript = %s,
                        vapi_summary = %s,
                        updated_at = now()
                    WHERE id = %s::uuid
                    """,
                    (transcript, vapi_summary, chat_id),
                )
                cur.execute(
                    """
                    UPDATE public.chat_ai_metadata
                    SET
                        sentiment = %s,
                        qa_evaluation = %s,
                        conversation_memory = COALESCE(%s::jsonb, conversation_memory),
                        ai_pipeline_status = %s,
                        ai_pipeline_error = %s,
                        updated_at = now()
                    WHERE chat_id = %s::uuid
                    """,
                    (
                        Json(sentiment) if sentiment is not None else None,
                        Json(qa_evaluation) if qa_evaluation is not None else None,
                        Json(conversation_memory)
                        if conversation_memory is not None
                        else None,
                        ai_pipeline_status,
                        ai_pipeline_error,
                        chat_id,
                    ),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print("UPDATE_POST_CALL_FAILED:", repr(e))
