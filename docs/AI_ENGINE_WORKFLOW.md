# AI engine workflow (phases 0–7)

This doc matches the implementation in `backend/` and `supabase/sql/003_ai_engine.sql`. Read it top to bottom once; then use it as a checklist while you configure Vapi and AWS.

---

## Phase 0 — Two ways to run the same pipeline

### A) Vapi webhook (automatic, production-shaped)

**What:** After a call ends, **Vapi’s servers** send an HTTP `POST` to **your** backend with a JSON body.

**Why:** Your app never “polls” Vapi. You get the transcript when it exists, reliably, at end of call.

**How:** You expose `POST /webhooks/vapi` on a **public URL** (deployed API or ngrok). In the Vapi dashboard you set a **Server URL** (sometimes called server/webhook URL) so Vapi knows where to POST. Your code checks `message.type === "end-of-call-report"`, reads `message.call.id` and `message.artifact.transcript`, finds the row in `leads` where `vapi_call_id` matches, then runs Bedrock agents and `UPDATE`s that row.

**B alongside A:** `POST /internal/replay-post-call` lets you paste a transcript and a `lead_id` (or `vapi_call_id`) to run the **same** pipeline without waiting for Vapi. **Why:** Local testing and demos when webhooks are awkward. **How:** Send header `x-debug-key: <POST_CALL_DEBUG_KEY>` (see env section at the end of your setup).

---

## Phase 1 — AWS

Use the **same** account/region as Titan embeddings. Grant **`bedrock:InvokeModel`** on your chat model or inference profile (Titan embeddings often use `bedrock:InvokeModel` already). Env vars are listed at the end of your own checklist (you asked to add `.env` last).

---

## Phase 2 — Database

**What:** New columns on `public.leads` store the rubric snapshot, transcript, agent JSON outputs, and pipeline status.

**Why:** The QA agent must see the **same** `kb_context` the assistant saw; that string is saved on insert. Post-call artifacts must live somewhere durable → Supabase.

**How:** Run `supabase/sql/003_ai_engine.sql` in the Supabase SQL editor (or your migration runner). Then new `INSERT`s from `persist_lead` include `kb_context` and optional `lead_ai_enrichment`.

---

## Phase 3 — Deferred

A larger shared “chat client” refactor can wait. Today, all Bedrock chat goes through `backend/agents/llm.py` (`converse_json` → `invoke_model` + Anthropic Messages body).

---

## Phase 4 — Agents (why / how)

| Module | Why | How |
|--------|-----|-----|
| `agents/sentiment_agent.py` | Reviewers want tone at a glance | One `converse_json` / `invoke_model` call; strict JSON shape in system prompt |
| `agents/qa_eval_agent.py` | Score answers vs rubric | Pass stored `kb_context` + transcript |
| `agents/memory_agent.py` | Next call continuity | Summarize + merge with prior `conversation_memory` JSON |
| `agents/lead_enrichment_agent.py` | CRM hints from the form only | One call on name/phone/role/experience (no transcript) |

---

## Phase 5 — Orchestrator

**File:** `backend/agents/orchestrator.py`

**Why:** One function so the webhook and debug route never drift apart.

**How:** `ThreadPoolExecutor(max_workers=2)` runs sentiment and QA **in parallel**; then **memory** runs after both finish (even if one failed).

---

## Phase 6 — Webhook clarity (simple mental model)

Think of three actors:

1. **Browser / form** → calls your `POST /lead` → you tell **Vapi** “start call” → you save `vapi_call_id` on the lead.
2. **Vapi + telephony** → runs the conversation (your assistant prompt + variables).
3. **When the call ends** → **Vapi** (not the user’s browser) → `POST`s to **`/webhooks/vapi`** on your server.

So the **webhook is server-to-server**: Vapi → your FastAPI. Your handler does not need the frontend. Match `message.call.id` to `leads.vapi_call_id` to know **which lead row** to update.

**Dashboard checklist:** Server URL = your public `.../webhooks/vapi`, and include **`end-of-call-report`** in server messages for that assistant/phone number (per [Vapi server events](https://docs.vapi.ai/server-url/events)).

---

## Phase 7 — Memory on the next call

**Why:** The candidate may call again; the assistant should not “forget” verified facts.

**How:** `GET`-style logic inside `POST /lead`: `fetch_conversation_memory_for_phone` loads the latest non-null `conversation_memory` for that phone and passes it to Vapi as variable `conversation_memory` (JSON text; `{}` if none). Update your Vapi assistant prompt to say: use this variable when non-empty.

---

## Phase 8 — Later

Integration tests, load tests, and hardening (queues, signatures) — as you planned.

---

## Env vars (when you add `.env`)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Already used; required for memory fetch + webhook DB updates |
| `BEDROCK_CHAT_MODEL_ID` | Optional `invoke_model` **modelId** override. If unset, `agents/llm.py` picks **Haiku 4.5 inference profile** from `AWS_REGION` (e.g. `us-east-1` → `us.anthropic.claude-haiku-4-5-20251001-v1:0`). The raw foundation id `anthropic.claude-haiku-4-5-20251001-v1:0` often errors: on-demand throughput isn’t supported. |
| `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Same pattern as embeddings |
| `VAPI_SERVER_SECRET` | Optional; if set, requests must send matching `x-vapi-secret` header |
| `POST_CALL_DEBUG_KEY` | Enables `/internal/replay-post-call`; send as `x-debug-key` |
| `VAPI_ALLOW_REPROCESS` | If `true`, webhook may run pipeline again even when `ai_pipeline_status` is `done` |

Optional tuning: `BEDROCK_CHAT_MAX_TOKENS`, `BEDROCK_CHAT_TEMPERATURE`, `BEDROCK_ANTHROPIC_VERSION` (default `bedrock-2023-05-31`; see `agents/llm.py`).
