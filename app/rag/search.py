from __future__ import annotations

# RAG L1/L2/L3 — orchestration; vector SQL nằm trong repositories.

import app.config.settings as _cfg
from app.ingest.processing.embeddings import embed_texts
from app.repositories.aspect_chunks import search_similar_chunks
from app.repositories.aspect_summaries import search_similar_summaries
from app.repositories.raw_reviews import get_raw_reviews as repo_get_raw_reviews


def _coverage(score: float, has_items: bool) -> str:
    if not has_items:
        return "none"
    if score >= _cfg.RAG_MIN_SCORE:
        return "sufficient"
    return "partial"


async def search_aspect_summary(
    product_id: str,
    query: str,
    *,
    aspect: str | None = None,
    top_k: int | None = None,
) -> dict:
    k = top_k or _cfg.RAG_TOP_K
    query_vector = (await embed_texts([query]))[0]
    items = await search_similar_summaries(
        product_id, query_vector, aspect=aspect, limit=k
    )
    best = float(items[0]["score"]) if items else 0.0
    return {"coverage": _coverage(best, bool(items)), "items": items}


async def search_aspect_evidence(
    product_id: str,
    query: str,
    *,
    aspect: str | None = None,
    top_k: int | None = None,
) -> dict:
    k = top_k or _cfg.RAG_TOP_K
    query_vector = (await embed_texts([query]))[0]
    items = await search_similar_chunks(
        product_id, query_vector, aspect=aspect, limit=k
    )
    best = float(items[0]["score"]) if items else 0.0
    return {"coverage": _coverage(best, bool(items)), "items": items}


async def get_raw_reviews(
    product_id: str,
    *,
    limit: int = 10,
) -> dict:
    items = await repo_get_raw_reviews(product_id, limit=limit)
    return {"coverage": "sufficient" if items else "none", "items": items}
