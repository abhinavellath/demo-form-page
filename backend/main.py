"""
FastAPI entry — lead intake, Vapi outbound call, post-call webhook (Phase 6),
and optional debug replay (Phase 0-B).
"""
from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests

from agents.orchestrator import run_lead_enrichment_safe, run_post_call_pipeline
from leads_db import (
    fetch_conversation_memory_for_phone,
    find_lead_by_id,
    find_lead_by_vapi_call_id,
    persist_lead,
    update_lead_post_call_results,
)
from rag import retrieve_kb_context

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VAPI_API_KEY = os.getenv("VAPI_API_KEY")
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID")
VAPI_PHONE_NUMBER_ID = os.getenv("VAPI_PHONE_NUMBER_ID")
VAPI_SERVER_SECRET = os.getenv("VAPI_SERVER_SECRET", "").strip()
POST_CALL_DEBUG_KEY = os.getenv("POST_CALL_DEBUG_KEY", "").strip()
VAPI_ALLOW_REPROCESS = os.getenv("VAPI_ALLOW_REPROCESS", "").lower() in ("1", "true", "yes")


class Lead(BaseModel):
    name: str
    phone: str
    role: str
    experience: str


class ReplayPostCallBody(BaseModel):
    """Phase 0-B: replay agents without Vapi (manual transcript)."""

    transcript: str
    lead_id: str | None = None
    vapi_call_id: str | None = None
    force: bool = False


def _assert_vapi_server_secret(x_vapi_secret: str | None) -> None:
    """
    When VAPI_SERVER_SECRET is set in the dashboard, validate inbound webhooks.
    Vapi commonly forwards this as the `x-vapi-secret` header (confirm in your dashboard).
    """
    if not VAPI_SERVER_SECRET:
        return
    got = (x_vapi_secret or "").strip()
    if got != VAPI_SERVER_SECRET:
        raise HTTPException(status_code=401, detail="invalid server secret")


def _parse_end_of_call_report(body: dict[str, Any]) -> tuple[str | None, str, str | None]:
    """
    Vapi Server URL payload: top-level { "message": { "type": "end-of-call-report", ... } }.
    Returns (vapi_call_id, transcript, summary).
    """
    msg = body.get("message")
    if not isinstance(msg, dict):
        return None, "", None
    if msg.get("type") != "end-of-call-report":
        return None, "", None

    call = msg.get("call") or {}
    raw_id = call.get("id")
    call_id = str(raw_id) if raw_id is not None else None

    artifact = msg.get("artifact") or {}
    transcript = artifact.get("transcript") or msg.get("transcript") or ""
    if isinstance(transcript, list):
        transcript = "\n".join(str(x) for x in transcript)
    transcript = str(transcript).strip()

    summ = msg.get("summary")
    summary = str(summ) if summ is not None else None
    return call_id, transcript, summary


def _normalize_prior_memory(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            val = json.loads(raw)
            return val if isinstance(val, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _final_pipeline_status(out: dict[str, Any]) -> str:
    s, q, m = out.get("sentiment"), out.get("qa_evaluation"), out.get("conversation_memory")
    if s is None and q is None and m is None:
        return "failed"
    return "done"


def process_post_call(
    *,
    lead: dict[str, Any],
    transcript: str,
    vapi_summary: str | None,
    force: bool,
) -> dict[str, Any]:
    """
    Runs Bedrock agents and persists to the lead row.
    Idempotent: if ai_pipeline_status is already 'done', skip unless force or VAPI_ALLOW_REPROCESS.
    """
    if (
        not force
        and not VAPI_ALLOW_REPROCESS
        and (lead.get("ai_pipeline_status") or "") == "done"
    ):
        return {"status": "skipped", "reason": "already_done"}

    if not transcript.strip():
        update_lead_post_call_results(
            lead_id=lead["id"],
            transcript="",
            vapi_summary=vapi_summary,
            sentiment=None,
            qa_evaluation=None,
            conversation_memory=None,
            ai_pipeline_status="skipped",
            ai_pipeline_error="empty_transcript",
        )
        return {"status": "skipped", "reason": "empty_transcript"}

    prior = _normalize_prior_memory(lead.get("conversation_memory"))
    kb = lead.get("kb_context")
    kb_str = kb if isinstance(kb, str) else None

    out = run_post_call_pipeline(
        transcript=transcript,
        kb_context=kb_str,
        candidate_name=str(lead.get("name") or ""),
        role=str(lead.get("role") or ""),
        prior_memory=prior,
    )
    st = _final_pipeline_status(out)
    err = "; ".join(out.get("errors") or []) if out.get("errors") else None

    update_lead_post_call_results(
        lead_id=lead["id"],
        transcript=transcript,
        vapi_summary=vapi_summary,
        sentiment=out.get("sentiment"),
        qa_evaluation=out.get("qa_evaluation"),
        conversation_memory=out.get("conversation_memory"),
        ai_pipeline_status=st,
        ai_pipeline_error=err,
    )
    return {"status": st, "errors": out.get("errors") or []}


@app.get("/")
async def root():
    return {"message": "Backend running"}


@app.post("/lead")
async def receive_lead(data: Lead):
    print("===== NEW LEAD RECEIVED =====")
    print("Name:", data.name)
    print("Phone:", data.phone)
    print("Role:", data.role)
    print("Experience:", data.experience)
    print("=============================")

    kb_context, rag_meta = retrieve_kb_context(
        role=data.role,
        experience=data.experience,
        name=data.name,
    )
    print("RAG:", json.dumps(rag_meta, default=str))

    memory_for_vapi = fetch_conversation_memory_for_phone(data.phone)
    lead_ai_enrichment = run_lead_enrichment_safe(
        name=data.name,
        phone=data.phone,
        role=data.role,
        experience=data.experience,
    )

    variable_values: dict[str, str] = {
        "candidate_name": data.name,
        "role": data.role,
        "experience": data.experience,
        "kb_context": kb_context,
        "conversation_memory": memory_for_vapi or "{}",
    }

    payload = {
        "assistantId": VAPI_ASSISTANT_ID,
        "phoneNumberId": VAPI_PHONE_NUMBER_ID,
        "customer": {"number": data.phone, "name": data.name},
        "assistantOverrides": {"variableValues": variable_values},
    }

    headers = {
        "Authorization": f"Bearer {VAPI_API_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.post("https://api.vapi.ai/call", json=payload, headers=headers)
    print(response.text)

    persist_lead(
        name=data.name,
        phone=data.phone,
        role=data.role,
        experience=data.experience,
        rag_meta=rag_meta,
        kb_context=kb_context,
        lead_ai_enrichment=lead_ai_enrichment,
        vapi_http_status=response.status_code,
        vapi_response_text=response.text,
    )

    return {"message": f"AI recruiter is calling {data.name}"}


@app.post("/webhooks/vapi")
async def vapi_server_webhook(
    request: Request,
    x_vapi_secret: str | None = Header(default=None, alias="x-vapi-secret"),
):
    """
    Phase 6 (A): Vapi calls YOUR URL when something happens on a call.
    We only act on `end-of-call-report` — that is when transcript + summary exist.

    Why: your laptop is not on the call; Vapi's cloud is. When the call ends, Vapi
    POSTs JSON to this route so your database can be updated without you polling.

    How: match `call.id` to `leads.vapi_call_id` saved when /lead started the call,
    then run the same post-call pipeline as the debug route.
    """
    _assert_vapi_server_secret(x_vapi_secret)
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid json: {exc}") from exc

    if not isinstance(body, dict):
        return {"ok": True, "ignored": True}

    call_id, transcript, summary = _parse_end_of_call_report(body)
    if call_id is None:
        return {"ok": True, "ignored": True}

    lead = find_lead_by_vapi_call_id(call_id)
    if not lead:
        return {"ok": True, "ignored": True, "detail": "lead_not_found_for_call_id"}

    result = process_post_call(
        lead=lead,
        transcript=transcript,
        vapi_summary=summary,
        force=False,
    )
    return {"ok": True, "call_id": call_id, "result": result}


@app.post("/internal/replay-post-call")
async def replay_post_call(
    body: ReplayPostCallBody,
    x_debug_key: str | None = Header(default=None, alias="x-debug-key"),
):
    """
    Phase 0-B: same agents as the webhook, but YOU send transcript (no Vapi needed).
    Protect with POST_CALL_DEBUG_KEY in header `x-debug-key`.
    """
    if not POST_CALL_DEBUG_KEY:
        raise HTTPException(
            status_code=503,
            detail="POST_CALL_DEBUG_KEY is not configured on the server",
        )
    if (x_debug_key or "") != POST_CALL_DEBUG_KEY:
        raise HTTPException(status_code=401, detail="invalid debug key")

    if not body.transcript.strip():
        raise HTTPException(status_code=400, detail="transcript is required")

    if body.lead_id:
        lead = find_lead_by_id(body.lead_id)
    elif body.vapi_call_id:
        lead = find_lead_by_vapi_call_id(body.vapi_call_id)
    else:
        raise HTTPException(
            status_code=400,
            detail="provide lead_id or vapi_call_id so we can load kb_context + prior memory",
        )

    if not lead:
        raise HTTPException(status_code=404, detail="lead not found")

    result = process_post_call(
        lead=lead,
        transcript=body.transcript,
        vapi_summary=None,
        force=body.force,
    )
    return {"ok": True, "result": result}
