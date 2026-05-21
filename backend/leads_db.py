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


def persist_lead(
    *,
    name: str,
    phone: str,
    role: str,
    experience: str,
    rag_meta: dict[str, Any],
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

    try:
        conn = psycopg2.connect(db_url, sslmode="require")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.leads (
                        name, phone, role, experience,
                        rag_meta, vapi_http_status, vapi_call_id, vapi_call_status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        name,
                        phone,
                        role,
                        experience,
                        Json(rag_meta),
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
