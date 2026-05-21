-- Run in Supabase SQL Editor after 001_kb_chunks.sql.
-- Stores one row per form submission for reporting / exports.

create table if not exists public.leads (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  name text not null,
  phone text not null,
  role text not null,
  experience text not null,
  rag_meta jsonb,
  vapi_http_status int,
  vapi_call_id text,
  vapi_call_status text,
  constraint leads_role_check check (role in ('DevOps Engineer', 'AI Engineer'))
);

create index if not exists leads_created_at_idx on public.leads (created_at desc);
create index if not exists leads_role_idx on public.leads (role);

comment on table public.leads is 'One row per POST /lead (demo CRM).';
