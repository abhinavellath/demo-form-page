# RAG setup (Supabase + Amazon Bedrock Titan embeddings)

Embeddings use **Amazon Bedrock** `amazon.titan-embed-text-v1` (**1536** dimensions), matching `vector(1536)` in `supabase/sql/001_kb_chunks.sql`. No column change when switching from OpenAI.

## Phase 1 — Supabase

1. Create a project at [supabase.com](https://supabase.com).
2. **SQL Editor** → run `supabase/sql/001_kb_chunks.sql`.
3. Build **`DATABASE_URL`** (direct Postgres, port **5432** recommended). See Supabase **Project Settings → Database**.

## Phase 2 — AWS Bedrock

1. **Region:** pick a region where **Titan Embeddings** is enabled (e.g. `us-east-1`). Set **`AWS_REGION`** to that value on Render and locally.
2. **Model access:** AWS console → **Bedrock** → **Model access** (or equivalent) → enable **`amazon.titan-embed-text-v1`**.
3. **IAM user** (for Render) with **`bedrock:InvokeModel`** on the foundation model ARN for Titan Embeddings v1 (scope can be tightened after it works).
4. Keys: **`AWS_ACCESS_KEY_ID`** + **`AWS_SECRET_ACCESS_KEY`** on Render (or use Render’s supported AWS integration if you move to roles later).

## Phase 3 — Ingest (local, manual)

**When to run:** after any edit to `kb/*.md`, or after switching embedding provider (always **re-ingest** so vectors are all Titan).

**What it does:** parses ` ```json ` blocks → deletes rows per affected role → **one Bedrock `invoke_model` per chunk`** → inserts into `kb_chunks`.

From **repo root**:

```bash
pip install -r backend/requirements.txt
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION=us-east-1
export DATABASE_URL=postgresql://...
python scripts/ingest_kb.py
```

Windows: `set VAR=value` instead of `export`.

Expect **Inserted 10 rows** (5 + 5) after first full ingest.

## Phase 4 — Render

Redeploy after `requirements.txt` change (`boto3` replaces `openai`).

Each `POST /lead`:

1. Logs the lead.
2. Titan-embeds the query string → pgvector search by `role` → `top_k = min(5, count)`.
3. Sends `kb_context` in Vapi `assistantOverrides.variableValues`.

## Phase 5 — Vapi prompt

Use `docs/vapi-system-prompt.md` in the **Recruiter Assistant** system prompt (`{{kb_context}}`).

## Environment variables

### Already on Render

- `VAPI_API_KEY`, `VAPI_ASSISTANT_ID`, `VAPI_PHONE_NUMBER_ID`

### RAG + Bedrock

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | Supabase Postgres URI. |
| `AWS_ACCESS_KEY_ID` | Yes | IAM user access key for Bedrock invoke. |
| `AWS_SECRET_ACCESS_KEY` | Yes | IAM secret. |
| `AWS_REGION` | Yes | Region where Titan v1 is enabled (e.g. `us-east-1`). |
| `BEDROCK_EMBEDDING_MODEL_ID` | No | Default `amazon.titan-embed-text-v1`. |
| `RAG_ENABLED` | No | Default `true`. Set `false` to skip retrieval. |

Optional: `AWS_SESSION_TOKEN` if using temporary credentials (boto3 reads it automatically when set).

### Removed (OpenAI path)

- ~~`OPENAI_API_KEY`~~ — not used for RAG anymore.
- ~~`EMBEDDING_MODEL`~~ — Titan model id is **`BEDROCK_EMBEDDING_MODEL_ID`** or the default above.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| `embed_failed` / AccessDenied | IAM policy includes `bedrock:InvokeModel`; model access enabled in console; **region** matches model. |
| Wrong embedding length | Must stay **1536** for `amazon.titan-embed-text-v1` and current SQL. |
| `no_rows_for_role` | Run `ingest_kb.py`; verify rows in Supabase **kb_chunks**. |
| Mixed old vectors | After any embedding provider change, **re-run ingest** for all roles. |

## Leads table (form submissions)

1. In Supabase **SQL Editor**, run `supabase/sql/002_leads.sql` (after `001_kb_chunks.sql`).
2. Uses the same **`DATABASE_URL`** as RAG — no extra env vars.
3. Each **`POST /lead`** inserts one row into **`public.leads`**: `name`, `phone`, `role`, `experience`, `rag_meta` (JSON), `vapi_http_status`, and when the Vapi body is JSON, `vapi_call_id` + `vapi_call_status`. If the insert fails, the handler still returns the normal response and logs **`LEAD_PERSIST_FAILED`**.

**View:** Supabase **Table Editor → leads**, or SQL: `select * from public.leads order by created_at desc limit 50;`
