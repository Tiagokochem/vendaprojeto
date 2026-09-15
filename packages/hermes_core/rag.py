"""RAG leve: embeddings OpenAI + cosine em Python (sem pgvector)."""
from __future__ import annotations

import json
import logging
import math
import urllib.error
import urllib.request
from dataclasses import dataclass

from hermes_core.llm import configured

log = logging.getLogger("hermes_core.rag")

DEFAULT_EMBED_MODEL = "text-embedding-3-small"


@dataclass
class KbHit:
    question: str
    answer: str
    score: float
    method: str  # embedding | keyword


def embed_texts(
    *,
    api_key: str,
    texts: list[str],
    model: str = DEFAULT_EMBED_MODEL,
    timeout: int = 30,
) -> list[list[float]] | None:
    if not configured(api_key) or not texts:
        return None
    body = {"model": model, "input": [t[:6000] for t in texts]}
    req = urllib.request.Request(
        "https://api.openai.com/v1/embeddings",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key.strip()}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        log.warning("embeddings falhou: %s", exc)
        return None
    try:
        data = sorted(raw["data"], key=lambda d: d["index"])
        return [d["embedding"] for d in data]
    except (KeyError, TypeError):
        return None


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def keyword_score(query: str, question: str, answer: str) -> float:
    q_tokens = {t for t in query.lower().split() if len(t) > 2}
    if not q_tokens:
        return 0.0
    blob = f"{question} {answer}".lower()
    hits = sum(1 for t in q_tokens if t in blob)
    return hits / len(q_tokens)


def rank_entries(
    *,
    query: str,
    entries: list[dict],
    query_embedding: list[float] | None = None,
    top_k: int = 3,
    min_score: float = 0.35,
) -> list[KbHit]:
    hits: list[KbHit] = []
    for e in entries:
        question = e.get("question") or ""
        answer = e.get("answer") or ""
        emb = e.get("embedding")
        score = 0.0
        method = "keyword"
        if query_embedding and isinstance(emb, list) and emb:
            score = cosine(query_embedding, emb)
            method = "embedding"
        else:
            score = keyword_score(query, question, answer)
        if score >= min_score:
            hits.append(KbHit(question=question, answer=answer, score=score, method=method))
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:top_k]
