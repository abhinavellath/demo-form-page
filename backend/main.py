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
from agents.recruiter_chat import (
    DEMO_CHAT_CONNECT_USER_MESSAGE,
    format_transcript_for_post_call,
    run_recruiter_opening,
    run_recruiter_turn,
)
import chat_session_store
from leads_db import (
    fetch_conversation_memory_for_phone,
    fetch_prior_conversation_memory_for_phone,
    find_post_call_context_by_chat_id,
    find_post_call_context_by_lead_id,
    find_post_call_context_by_vapi_call_id,
    persist_lead,
    persist_lead_chat_session,
    update_chat_post_call_results,
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
    """Replay agents without Vapi (manual transcript)."""

    transcript: str
    lead_id: str | None = None
    chat_id: str | None = None
    vapi_call_id: str | None = None
    force: bool = False


class ChatMessageBody(BaseModel):
    text: str


def _assert_vapi_server_secret(x_vapi_secret: str | None) -> None:
    if not VAPI_SERVER_SECRET:
        return
    got = (x_vapi_secret or "").strip()
    if got != VAPI_SERVER_SECRET:
        raise HTTPException(status_code=401, detail="invalid server secret")


def _parse_end_of_call_report(body: dict[str, Any]) -> tuple[str | None, str, str | None]:
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


def _final_pipeline_status(out: dict[str, Any]) -> str:
    s, q, m = out.get("sentiment"), out.get("qa_evaluation"), out.get("conversation_memory")
    if s is None and q is None and m is None:
        return "failed"
    return "done"


def process_post_call(
    *,
    ctx: dict[str, Any],
    transcript: str,
    vapi_summary: str | None,
    force: bool,
) -> dict[str, Any]:
    """
    Runs Bedrock agents and persists to chats + chat_ai_metadata for this chat_id.
    """
    chat_id = str(ctx["chat_id"])
    if (
        not force
        and not VAPI_ALLOW_REPROCESS
        and (ctx.get("ai_pipeline_status") or "") == "done"
    ):
        return {"status": "skipped", "reason": "already_done"}

    if not transcript.strip():
        update_chat_post_call_results(
            chat_id=chat_id,
            transcript="",
            vapi_summary=vapi_summary,
            sentiment=None,
            qa_evaluation=None,
            conversation_memory=None,
            ai_pipeline_status="skipped",
            ai_pipeline_error="empty_transcript",
        )
        return {"status": "skipped", "reason": "empty_transcript"}

    prior = fetch_prior_conversation_memory_for_phone(
        str(ctx.get("phone") or ""), exclude_chat_id=chat_id
    )

    kb = ctx.get("kb_context")
    kb_str = kb if isinstance(kb, str) else None

    out = run_post_call_pipeline(
        transcript=transcript,
        kb_context=kb_str,
        candidate_name=str(ctx.get("name") or ""),
        role=str(ctx.get("role") or ""),
        prior_memory=prior,
    )
    st = _final_pipeline_status(out)
    err = "; ".join(out.get("errors") or []) if out.get("errors") else None

    update_chat_post_call_results(
        chat_id=chat_id,
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


@app.post("/lead-chat")
async def start_lead_chat_session(data: Lead):
    """
    Text demo: persist lead + chat (no Vapi), return chat_id + session_secret + opening line.
    """
    kb_context, rag_meta = retrieve_kb_context(
        role=data.role,
        experience=data.experience,
        name=data.name,
    )
    memory_for_phone = fetch_conversation_memory_for_phone(data.phone)
    lead_ai_enrichment = run_lead_enrichment_safe(
        name=data.name,
        phone=data.phone,
        role=data.role,
        experience=data.experience,
    )

    persisted = persist_lead_chat_session(
        name=data.name,
        phone=data.phone,
        role=data.role,
        experience=data.experience,
        rag_meta=rag_meta,
        kb_context=kb_context,
        lead_ai_enrichment=lead_ai_enrichment,
    )
    if not persisted:
        raise HTTPException(
            status_code=503,
            detail="Could not start chat session (DATABASE_URL missing or persist failed).",
        )
    lead_id, chat_id = persisted

    session_secret = chat_session_store.create_session(chat_id)

    opening = run_recruiter_opening(
        candidate_name=data.name,
        role=data.role,
        experience=data.experience,
        kb_context=kb_context,
        prior_memory_json=memory_for_phone or None,
    )
    chat_session_store.set_opening_turns(
        chat_id,
        [
            ("user", DEMO_CHAT_CONNECT_USER_MESSAGE),
            ("assistant", opening),
        ],
    )

    return {
        "chat_id": chat_id,
        "lead_id": lead_id,
        "session_secret": session_secret,
        "opening_message": opening,
    }


@app.post("/chat/{chat_id}/message")
async def chat_demo_message(
    chat_id: str,
    body: ChatMessageBody,
    x_chat_session: str | None = Header(default=None, alias="x-chat-session"),
):
    if not chat_session_store.validate_secret(chat_id, x_chat_session):
        raise HTTPException(status_code=401, detail="invalid or missing x-chat-session")
    sess = chat_session_store.get_session(chat_id)
    if not sess:
        raise HTTPException(status_code=404, detail="chat session not found or expired")
    if sess.ended:
        raise HTTPException(status_code=400, detail="conversation has ended")
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    ctx = find_post_call_context_by_chat_id(chat_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="chat not found")

    memory_json = fetch_conversation_memory_for_phone(str(ctx.get("phone") or ""))
    try:
        reply = run_recruiter_turn(
            transcript_turns=sess.transcript_turns,
            user_message=text,
            candidate_name=str(ctx.get("name") or ""),
            role=str(ctx.get("role") or ""),
            experience=str(ctx.get("experience") or ""),
            kb_context=ctx.get("kb_context") if isinstance(ctx.get("kb_context"), str) else None,
            prior_memory_json=memory_json or None,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"recruiter model error: {exc}",
        ) from exc

    chat_session_store.append_user_and_assistant(chat_id, text, reply)
    return {"reply": reply}


@app.post("/chat/{chat_id}/end")
async def chat_demo_end(
    chat_id: str,
    x_chat_session: str | None = Header(default=None, alias="x-chat-session"),
):
    if not chat_session_store.validate_secret(chat_id, x_chat_session):
        raise HTTPException(status_code=401, detail="invalid or missing x-chat-session")
    sess = chat_session_store.get_session(chat_id)
    if not sess:
        raise HTTPException(status_code=404, detail="chat session not found or expired")

    if sess.post_call_ran:
        return {"ok": True, "result": {"status": "already_finalized"}}

    chat_session_store.set_ended(chat_id)
    transcript = format_transcript_for_post_call(sess.transcript_turns)

    ctx = find_post_call_context_by_chat_id(chat_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="chat not found")

    try:
        result = process_post_call(
            ctx=ctx,
            transcript=transcript,
            vapi_summary=None,
            force=False,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"post-call pipeline error: {exc}",
        ) from exc

    chat_session_store.mark_post_call_ran(chat_id)
    return {"ok": True, "result": result}


@app.post("/webhooks/vapi")
async def vapi_server_webhook(
    request: Request,
    x_vapi_secret: str | None = Header(default=None, alias="x-vapi-secret"),
):
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

    ctx = find_post_call_context_by_vapi_call_id(call_id)
    if not ctx:
        return {"ok": True, "ignored": True, "detail": "chat_not_found_for_call_id"}

    result = process_post_call(
        ctx=ctx,
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
    if not POST_CALL_DEBUG_KEY:
        raise HTTPException(
            status_code=503,
            detail="POST_CALL_DEBUG_KEY is not configured on the server",
        )
    if (x_debug_key or "") != POST_CALL_DEBUG_KEY:
        raise HTTPException(status_code=401, detail="invalid debug key")

    if not body.transcript.strip():
        raise HTTPException(status_code=400, detail="transcript is required")

    ctx = None
    if body.chat_id:
        ctx = find_post_call_context_by_chat_id(body.chat_id)
    elif body.lead_id:
        ctx = find_post_call_context_by_lead_id(body.lead_id)
    elif body.vapi_call_id:
        ctx = find_post_call_context_by_vapi_call_id(body.vapi_call_id)
    else:
        raise HTTPException(
            status_code=400,
            detail="provide chat_id, lead_id, or vapi_call_id",
        )

    if not ctx:
        raise HTTPException(status_code=404, detail="chat/lead not found")

    result = process_post_call(
        ctx=ctx,
        transcript=body.transcript,
        vapi_summary=None,
        force=body.force,
    )
    return {"ok": True, "result": result}
