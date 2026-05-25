-- Post-call AI pipeline + continuity (conversation memory).
-- Apply after 002_leads.sql.

alter table public.leads
  add column if not exists kb_context text,
  add column if not exists transcript text,
  add column if not exists vapi_summary text,
  add column if not exists conversation_memory jsonb,
  add column if not exists sentiment jsonb,
  add column if not exists qa_evaluation jsonb,
  add column if not exists lead_ai_enrichment jsonb,
  add column if not exists ai_pipeline_status text,
  add column if not exists ai_pipeline_error text;

comment on column public.leads.kb_context is 'RAG string passed to Vapi for this call; used by QA eval agent after the call.';
comment on column public.leads.transcript is 'Full transcript from Vapi end-of-call-report (artifact.transcript).';
comment on column public.leads.vapi_summary is 'Optional summary from Vapi end-of-call-report when present.';
comment on column public.leads.conversation_memory is 'Bedrock memory agent JSON for next interaction.';
comment on column public.leads.sentiment is 'Bedrock sentiment agent JSON.';
comment on column public.leads.qa_evaluation is 'Bedrock QA evaluation JSON vs kb_context.';
comment on column public.leads.lead_ai_enrichment is 'Bedrock lead enrichment JSON from form fields.';
comment on column public.leads.ai_pipeline_status is 'post_call pipeline: pending | done | failed | skipped';
comment on column public.leads.ai_pipeline_error is 'Last pipeline error message for debugging.';

create index if not exists leads_vapi_call_id_idx on public.leads (vapi_call_id);
create index if not exists leads_phone_created_idx on public.leads (phone, created_at desc);
