# RAG setup (Supabase + OpenAI embeddings)

## Phase 1 — Supabase

1. Create a project at [supabase.com](https://supabase.com).
2. **SQL Editor** → paste and run `supabase/sql/001_kb_chunks.sql`.
3. Copy the **database password** and build `DATABASE_URL`:
   - In Supabase: **Project Settings → Database**.
   - Use the **URI** mode connection string (direct Postgres, port **5432**), not the pooler, for fewer surprises with `pgvector` from Render/scripts.
   - Example shape:  
     `postgresql://postgres:<PASSWORD>@db.<PROJECT_REF>.supabase.co:5432/postgres`
   - Append `?sslmode=require` if your client does not default to SSL (psycopg2 uses `sslmode=require` in code).

## Phase 2 — Ingest (local, manual)

**When to run:** after any edit to `kb/*.md`, or after first creating the table.

**What it does:** parses every ` ```json ` … ` ``` ` block in `kb/*.md` (except `README.md`), validates `role`, batch-embeds with `text-embedding-3-small`, **deletes** existing `kb_chunks` rows for each role found, then **inserts** fresh rows.

From the **repo root** (`demo-page/`):

```bash
pip install -r backend/requirements.txt
set OPENAI_API_KEY=sk-...
set DATABASE_URL=postgresql://...
python scripts/ingest_kb.py
```

On macOS/Linux use `export` instead of `set`.

You should see per-file chunk counts and `Inserted 10 rows` (5 + 5).

## Phase 3–4 — Render

Add environment variables (see list below). Redeploy so `pip install` picks up `openai`, `psycopg2-binary`, `pgvector`.

Each `POST /lead` will:

1. Log the lead.
2. Run **call-start retrieval** (embed query → cosine search scoped by `role` → `top_k = min(5, count)`).
3. Pass `kb_context` into Vapi `assistantOverrides.variableValues` alongside `candidate_name`, `role`, `experience`.

## Phase 4 — Vapi assistant prompt

Copy the contents of `docs/vapi-system-prompt.md` into your **Recruiter Assistant** system prompt in the Vapi dashboard. It references `{{kb_context}}`.

## Phase 6 — Environment variables

### Already on Render

- `VAPI_API_KEY`
- `VAPI_ASSISTANT_ID`
- `VAPI_PHONE_NUMBER_ID`

### Add for RAG

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for **embeddings only** (same org as you use for `text-embedding-3-small`). |
| `DATABASE_URL` | Yes | Supabase Postgres connection string (direct / port 5432 recommended). |
| `RAG_ENABLED` | No | Default `true`. Set `false` to skip retrieval and send only the fallback `kb_context`. |
| `EMBEDDING_MODEL` | No | Default `text-embedding-3-small`. |

### Optional later

- `RAG_TOP_K` — not used in code today; top-k is fixed to **min(5, row count)** per your spec.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| `no_rows_for_role` in Render logs | Run `ingest_kb.py`; confirm rows in Supabase **Table Editor → kb_chunks**. |
| `db_failed` SSL | Use Supabase direct host; ensure password is URL-encoded if it has special characters. |
| Wrong questions for role | Form must send **exact** `DevOps Engineer` or `AI Engineer` (matches KB `role` and SQL filter). |
| `embed_failed` | `OPENAI_API_KEY` billing / quota on OpenAI. |
