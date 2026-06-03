# Data model: leads, chats, chat_ai_metadata

## Why three tables

| Table | Purpose |
|-------|---------|
| **`public.leads`** | CRM identity from the form: who applied, phone, role, experience. One row per form submit. |
| **`public.chats`** | **One row per call** (Vapi conversation): `vapi_call_id`, `kb_context` snapshot, **transcript**, **vapi_summary**, HTTP/status from call creation. This is your **chat history** timeline (`ORDER BY created_at`). |
| **`public.chat_ai_metadata`** | **Exactly one row per chat** (`chat_id` unique): RAG diagnostics, lead enrichment JSON, post-call outputs (`sentiment`, `qa_evaluation`, `conversation_memory`), pipeline status/errors. Keeps “AI blobs” off the lead row and off the transcript table. |

Relationships: `leads (1) ──< chats (many)` and `chats (1) ── chat_ai_metadata (1)`.

## SQL files

1. Run **`004_chats_and_metadata.sql`** — creates `chats` and `chat_ai_metadata`.
2. If you already had denormalized columns on **`leads`** (from `003_ai_engine.sql`), run **`004b_migrate_denormalized_leads.sql`**, verify counts, then **`004c_strip_leads_columns.sql`** to drop moved columns from `leads`.
3. Greenfield: use **`002_leads.sql`** (core columns only) + **`004`**. Skip `003` on new environments, or run `003` then `004b` + `004c` to normalize.

## API behavior

- **`POST /lead`**: `INSERT` lead → `INSERT` chat (with `kb_context`, Vapi ids) → `INSERT` `chat_ai_metadata` (RAG meta + enrichment).
- **Webhook / replay**: resolve row by **`chats.vapi_call_id`** or latest chat for **`lead_id`**, update **`chats`** (transcript, summary) and **`chat_ai_metadata`** (agents).
- **Memory for next call**: latest `conversation_memory` for the same **`leads.phone`** across all chats.

## Replay debug body

You may pass **`chat_id`** (preferred), **`lead_id`** (latest chat), or **`vapi_call_id`**.
