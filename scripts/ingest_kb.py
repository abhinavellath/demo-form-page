#!/usr/bin/env python3
"""
Load kb/*.md (fenced ```json blocks), embed with OpenAI text-embedding-3-small,
upsert into Supabase Postgres + pgvector table public.kb_chunks.

Run manually when KB markdown changes (no CI).

Usage (from repo root):
  cd demo-page
  pip install -r backend/requirements.txt
  set OPENAI_API_KEY=...
  set DATABASE_URL=postgresql://...   (Supabase: use direct connection string, SSL)
  python scripts/ingest_kb.py

What it does:
  1. Parses all ```json ... ``` blocks from kb/devops_engineer.md and kb/ai_engineer.md
  2. Validates role field matches DevOps Engineer | AI Engineer
  3. Deletes existing kb_chunks rows for each role present in the files (clean reload)
  4. Batch-embeds all chunk embedding_text values in one OpenAI call
  5. Inserts rows with 1536-dim vectors
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "kb"

# Load .env from backend/ if present
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / "backend" / ".env")
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

ALLOWED_ROLES = {"DevOps Engineer", "AI Engineer"}
EMBEDDING_MODEL = "text-embedding-3-small"
JSON_BLOCK = re.compile(r"```json\s*([\s\S]*?)\s*```", re.IGNORECASE)


def chunk_to_embedding_text(chunk: dict) -> str:
    good = chunk.get("good_signals") or []
    bad = chunk.get("bad_signals") or []
    follow = chunk.get("follow_ups") or []
    return "\n".join(
        [
            f"Role: {chunk.get('role', '')}",
            f"Topic: {chunk.get('topic', '')}",
            f"Question: {chunk.get('question', '')}",
            f"Purpose: {chunk.get('why_this_is_asked', '')}",
            "Good signals: " + "; ".join(str(x) for x in good),
            "Bad signals: " + "; ".join(str(x) for x in bad),
            "Follow-ups: " + "; ".join(str(x) for x in follow),
        ]
    )


def parse_md(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    chunks: list[dict] = []
    for raw in JSON_BLOCK.findall(text):
        raw = raw.strip()
        if not raw:
            continue
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError(f"Non-object JSON in {path.name}")
        role = obj.get("role")
        if role not in ALLOWED_ROLES:
            raise ValueError(f"Invalid role in {path.name}: {role!r}")
        for key in (
            "topic",
            "question",
            "why_this_is_asked",
            "good_signals",
            "bad_signals",
            "follow_ups",
        ):
            if key not in obj:
                raise ValueError(f"Missing {key} in {path.name}")
        chunks.append(obj)
    return chunks


def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    db_url = os.getenv("DATABASE_URL")
    if not api_key or not db_url:
        print("Set OPENAI_API_KEY and DATABASE_URL in the environment (or backend/.env).", file=sys.stderr)
        sys.exit(1)

    md_files = sorted(KB_DIR.glob("*.md"))
    if not md_files:
        print(f"No markdown files under {KB_DIR}", file=sys.stderr)
        sys.exit(1)

    all_chunks: list[dict] = []
    for md in md_files:
        if md.name.lower() == "readme.md":
            continue
        parsed = parse_md(md)
        print(f"{md.name}: {len(parsed)} JSON chunks")
        all_chunks.extend(parsed)

    if not all_chunks:
        print("No chunks parsed.", file=sys.stderr)
        sys.exit(1)

    roles_in_batch = {c["role"] for c in all_chunks}
    texts = [chunk_to_embedding_text(c) for c in all_chunks]

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    emb = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    vectors = [d.embedding for d in emb.data]
    if len(vectors) != len(all_chunks):
        print("Embedding count mismatch", file=sys.stderr)
        sys.exit(1)

    import psycopg2
    from pgvector.psycopg2 import register_vector

    conn = psycopg2.connect(db_url, sslmode="require")
    register_vector(conn)
    try:
        with conn.cursor() as cur:
            for role in roles_in_batch:
                cur.execute("DELETE FROM kb_chunks WHERE role = %s", (role,))
                print(f"Deleted existing rows for role={role!r}")

            for chunk, vec in zip(all_chunks, vectors, strict=True):
                etext = chunk_to_embedding_text(chunk)
                cur.execute(
                    """
                    INSERT INTO kb_chunks (role, topic, chunk_json, embedding_text, embedding)
                    VALUES (%s, %s, %s::jsonb, %s, %s)
                    """,
                    (
                        chunk["role"],
                        chunk["topic"],
                        json.dumps(chunk),
                        etext,
                        vec,
                    ),
                )
        conn.commit()
        print(f"Inserted {len(all_chunks)} rows into kb_chunks.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
