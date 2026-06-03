-- OPTIONAL: one-time migration when public.leads still has vapi/kb/transcript/AI columns (e.g. after 003).
-- Run AFTER 004_chats_and_metadata.sql. Verify row counts, then run 004c_strip_leads_columns.sql.

insert into public.chats (
  lead_id, vapi_call_id, vapi_create_http_status, vapi_call_status,
  kb_context, transcript, vapi_summary, created_at, updated_at
)
select
  l.id,
  l.vapi_call_id,
  l.vapi_http_status,
  l.vapi_call_status,
  l.kb_context,
  l.transcript,
  l.vapi_summary,
  l.created_at,
  now()
from public.leads l
where l.vapi_call_id is not null
  and not exists (select 1 from public.chats c where c.vapi_call_id = l.vapi_call_id);

insert into public.chat_ai_metadata (
  chat_id, rag_meta, lead_ai_enrichment, sentiment, qa_evaluation,
  conversation_memory, ai_pipeline_status, ai_pipeline_error
)
select
  c.id,
  l.rag_meta,
  l.lead_ai_enrichment,
  l.sentiment,
  l.qa_evaluation,
  l.conversation_memory,
  l.ai_pipeline_status,
  l.ai_pipeline_error
from public.leads l
join public.chats c on c.lead_id = l.id and c.vapi_call_id = l.vapi_call_id
where not exists (select 1 from public.chat_ai_metadata m where m.chat_id = c.id);
