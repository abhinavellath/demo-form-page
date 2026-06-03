-- OPTIONAL: run only after 004b backfill verified. Removes denormalized columns from public.leads.
-- Requires those columns to exist (from 003). If a column is already gone, statement is skipped.

alter table public.leads drop column if exists rag_meta;
alter table public.leads drop column if exists kb_context;
alter table public.leads drop column if exists transcript;
alter table public.leads drop column if exists vapi_summary;
alter table public.leads drop column if exists conversation_memory;
alter table public.leads drop column if exists sentiment;
alter table public.leads drop column if exists qa_evaluation;
alter table public.leads drop column if exists lead_ai_enrichment;
alter table public.leads drop column if exists ai_pipeline_status;
alter table public.leads drop column if exists ai_pipeline_error;
alter table public.leads drop column if exists vapi_call_id;
alter table public.leads drop column if exists vapi_call_status;
alter table public.leads drop column if exists vapi_http_status;
