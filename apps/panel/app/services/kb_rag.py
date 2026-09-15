"""Busca e indexação da KB do tenant (S5)."""
from __future__ import annotations

from hermes_core.llm import configured
from hermes_core.rag import DEFAULT_EMBED_MODEL, embed_texts, rank_entries
from psycopg.types.json import Json

from app import db
from app.config import settings


def ensure_embedding_columns() -> None:
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "ALTER TABLE agente.knowledge_entries ADD COLUMN IF NOT EXISTS embedding JSONB"
            )
            cur.execute(
                "ALTER TABLE agente.knowledge_entries ADD COLUMN IF NOT EXISTS embedded_at TIMESTAMPTZ"
            )


def index_entry(tenant_id: str, entry_id: int) -> bool:
    if not configured(settings.openai_api_key):
        return False
    row = db.fetch_one(
        """
        SELECT id, question, answer FROM agente.knowledge_entries
        WHERE id = %s AND tenant_id = %s AND approved AND NOT deprecated
        """,
        (entry_id, tenant_id),
    )
    if not row:
        return False
    text = f"{row['question']}\n{row['answer']}"
    vectors = embed_texts(api_key=settings.openai_api_key, texts=[text], model=DEFAULT_EMBED_MODEL)
    if not vectors:
        return False
    db.execute(
        """
        UPDATE agente.knowledge_entries
        SET embedding = %s, embedded_at = NOW()
        WHERE id = %s AND tenant_id = %s
        """,
        (Json(vectors[0]), entry_id, tenant_id),
    )
    return True


def reindex_tenant(tenant_id: str, limit: int = 100) -> dict:
    ensure_embedding_columns()
    if not configured(settings.openai_api_key):
        return {"ok": False, "reason": "llm_not_configured", "indexed": 0}

    rows = db.fetch_all(
        """
        SELECT id, question, answer FROM agente.knowledge_entries
        WHERE tenant_id = %s AND approved AND NOT deprecated
          AND (embedding IS NULL OR embedded_at IS NULL)
        ORDER BY id
        LIMIT %s
        """,
        (tenant_id, limit),
    )
    if not rows:
        return {"ok": True, "indexed": 0}

    texts = [f"{r['question']}\n{r['answer']}" for r in rows]
    vectors = embed_texts(api_key=settings.openai_api_key, texts=texts, model=DEFAULT_EMBED_MODEL)
    if not vectors or len(vectors) != len(rows):
        return {"ok": False, "reason": "embed_failed", "indexed": 0}

    indexed = 0
    for row, vec in zip(rows, vectors):
        db.execute(
            """
            UPDATE agente.knowledge_entries
            SET embedding = %s, embedded_at = NOW()
            WHERE id = %s AND tenant_id = %s
            """,
            (Json(vec), row["id"], tenant_id),
        )
        indexed += 1
    return {"ok": True, "indexed": indexed}


def search(tenant_id: str, query: str, top_k: int = 3) -> list[dict]:
    """Retorna snippets [{answer, question, score, method}]."""
    ensure_embedding_columns()
    entries = db.fetch_all(
        """
        SELECT id, question, answer, embedding
        FROM agente.knowledge_entries
        WHERE tenant_id = %s AND approved AND NOT deprecated
        ORDER BY created_at DESC
        LIMIT 100
        """,
        (tenant_id,),
    )
    query_emb = None
    if configured(settings.openai_api_key) and any(e.get("embedding") for e in entries):
        vectors = embed_texts(
            api_key=settings.openai_api_key,
            texts=[query],
            model=DEFAULT_EMBED_MODEL,
        )
        if vectors:
            query_emb = vectors[0]

    # Normalize embedding from JSON
    for e in entries:
        emb = e.get("embedding")
        if isinstance(emb, str):
            try:
                e["embedding"] = json_loads(emb)
            except Exception:  # noqa: BLE001
                e["embedding"] = None

    hits = rank_entries(
        query=query,
        entries=entries,
        query_embedding=query_emb,
        top_k=top_k,
        min_score=0.28 if query_emb else 0.2,
    )
    return [
        {"question": h.question, "answer": h.answer, "score": round(h.score, 4), "method": h.method}
        for h in hits
    ]


def json_loads(raw: str):
    import json

    return json.loads(raw)
