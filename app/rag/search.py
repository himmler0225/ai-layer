from __future__ import annotations
import app.config.settings as settings
from app.ingest.processing.embeddings import embed_texts
from app.repositories.aspect_chunks import search_similar_chunks
from app.repositories.aspect_summaries import search_similar_summaries
from app.repositories.raw_reviews import get_raw_reviews as repo_get_raw_reviews

def _coverage(score: float, has_items: bool) -> str:
    """(Nội bộ) Coverage `_coverage`.

    Args:
        score: (float) Tham số `score`.
        has_items: (bool) Tham số `has_items`.

    Returns:
        (str) Kết quả trả về."""
    if not has_items:
        return 'none'
    if score >= settings.RAG_MIN_SCORE:
        return 'sufficient'
    return 'partial'

async def search_aspect_summary(movie_id: str, query: str, *, aspect: str | None=None, top_k: int | None=None) -> dict:
    """Tìm kiếm aspect summary (async).

    Args:
        movie_id: (str) Tham số `movie_id`.
        query: (str) Tham số `query`.
        aspect: (str | None, mặc định None) Tham số `aspect`.
        top_k: (int | None, mặc định None) Tham số `top_k`.

    Returns:
        (dict) Kết quả trả về."""
    k = top_k or settings.RAG_TOP_K
    query_vector = (await embed_texts([query]))[0]
    items = await search_similar_summaries(movie_id, query_vector, aspect=aspect, limit=k)
    best = float(items[0]['score']) if items else 0.0
    return {'coverage': _coverage(best, bool(items)), 'items': items}

async def search_aspect_evidence(movie_id: str, query: str, *, aspect: str | None=None, top_k: int | None=None) -> dict:
    """Tìm kiếm aspect evidence (async).

    Args:
        movie_id: (str) Tham số `movie_id`.
        query: (str) Tham số `query`.
        aspect: (str | None, mặc định None) Tham số `aspect`.
        top_k: (int | None, mặc định None) Tham số `top_k`.

    Returns:
        (dict) Kết quả trả về."""
    k = top_k or settings.RAG_TOP_K
    query_vector = (await embed_texts([query]))[0]
    items = await search_similar_chunks(movie_id, query_vector, aspect=aspect, limit=k)
    best = float(items[0]['score']) if items else 0.0
    return {'coverage': _coverage(best, bool(items)), 'items': items}

async def get_raw_reviews(movie_id: str, *, limit: int=10) -> dict:
    """Lấy raw reviews (async).

    Args:
        movie_id: (str) Tham số `movie_id`.
        limit: (int, mặc định 10) Tham số `limit`.

    Returns:
        (dict) Kết quả trả về."""
    items = await repo_get_raw_reviews(movie_id, limit=limit)
    return {'coverage': 'sufficient' if items else 'none', 'items': items}
