-- Run this in Supabase: SQL Editor → New query → Run once.
-- Project: enable pgvector + screening chunks table.

create extension if not exists vector;

create table if not exists public.kb_chunks (
  id uuid primary key default gen_random_uuid(),
  role text not null check (role in ('DevOps Engineer', 'AI Engineer')),
  topic text not null,
  chunk_json jsonb not null,
  embedding_text text not null,
  embedding vector(1536) not null,
  created_at timestamptz not null default now()
);

create index if not exists kb_chunks_role_idx on public.kb_chunks (role);

-- Optional later: CREATE INDEX ON kb_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

comment on table public.kb_chunks is 'Role-tagged screening chunks for call-start RAG (text-embedding-3-small, 1536 dims).';
