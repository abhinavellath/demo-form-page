#!/usr/bin/env python3
"""
Load kb/*.md (fenced ```json blocks), embed with Amazon Bedrock
amazon.titan-embed-text-v1 (1536-dim), upsert into Supabase + pgvector.

Run manually when KB markdown changes (no CI).

Usage (from repo root):
  pip install -r backend/requirements.txt
  set AWS_ACCESS_KEY_ID=...
  set AWS_SECRET_ACCESS_KEY=...
  set AWS_REGION=us-east-1
  set DATABASE_URL=postgresql://...
  python scripts/ingest_kb.py

What it does:
  1. Parses all ```json ... ``` blocks from kb/*.md (except README.md)
  2. Validates role field matches DevOps Engineer | AI Engineer
  3. Deletes existing kb_chunks rows for each role present in the files (clean reload)
  4. Calls Bedrock Titan v1 once per chunk (invoke_model)
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
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Load .env from backend/ if present
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / "backend" / ".env")
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

ALLOWED_ROLES = {"DevOps Engineer", "AI Engineer"}
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
    ak = os.getenv("AWS_ACCESS_KEY_ID")
    sk = os.getenv("AWS_SECRET_ACCESS_KEY")
    db_url = os.getenv("DATABASE_URL")
    if not ak or not sk or not db_url:
        print(
            "Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and DATABASE_URL "
            "(and AWS_REGION, e.g. us-east-1) in the environment or backend/.env.",
            file=sys.stderr,
        )
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

    from embeddings import embed_titan_v1_batch

    vectors = embed_titan_v1_batch(texts)
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
