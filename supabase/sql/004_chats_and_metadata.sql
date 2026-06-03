-- Normalize storage: leads = CRM only; chats = per-call transcript + summary;
-- chat_ai_metadata = 1:1 AI outputs per chat.
-- Run after 002_leads.sql (and 003 if you used it). Then run 004b if you need to move old rows.

create table if not exists public.chats (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid not null references public.leads (id) on delete cascade,
  vapi_call_id text unique,
  vapi_create_http_status int,
  vapi_call_status text,
  kb_context text,
  transcript text,
  vapi_summary text,
  ended_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists chats_lead_id_idx on public.chats (lead_id);
create index if not exists chats_lead_created_idx on public.chats (lead_id, created_at desc);
create index if not exists chats_vapi_call_id_idx on public.chats (vapi_call_id);

comment on table public.chats is 'One row per screening call; transcript + Vapi summary for history.';
comment on column public.chats.kb_context is 'RAG string used on this call (QA eval compares transcript to this).';

create table if not exists public.chat_ai_metadata (
  id uuid primary key default gen_random_uuid(),
  chat_id uuid not null references public.chats (id) on delete cascade,
  rag_meta jsonb,
  lead_ai_enrichment jsonb,
  sentiment jsonb,
  qa_evaluation jsonb,
  conversation_memory jsonb,
  ai_pipeline_status text,
  ai_pipeline_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint chat_ai_metadata_chat_unique unique (chat_id)
);

create index if not exists chat_ai_metadata_pipeline_idx on public.chat_ai_metadata (ai_pipeline_status);

comment on table public.chat_ai_metadata is '1:1 Bedrock/RAG outputs per chat (enrichment + post-call agents).';

comment on table public.leads is 'CRM lead (form submit). Call transcripts and AI outputs live in chats + chat_ai_metadata.';
