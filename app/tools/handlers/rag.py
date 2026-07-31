from typing import Any

from app.rag import search as rag_search
from app.rag.config import RAG_ENABLED


async def search_movie_summary(inp: dict) -> Any:
    """Search movie summary (async).

    Args:
        inp: (dict) Tham số `inp`.

    Returns:
        (Any) Kết quả trả về."""
    return await rag_search.search_aspect_summary(
        inp["movie_id"], inp["query"], aspect=inp.get("aspect")
    )


async def search_aspect_evidence(inp: dict) -> Any:
    """Search aspect evidence (async).

    Args:
        inp: (dict) Tham số `inp`.

    Returns:
        (Any) Kết quả trả về."""
    return await rag_search.search_aspect_evidence(
        inp["movie_id"], inp["query"], aspect=inp.get("aspect")
    )


async def get_raw_reviews(inp: dict) -> Any:
    """Lấy raw reviews (async).

    Args:
        inp: (dict) Tham số `inp`.

    Returns:
        (Any) Kết quả trả về."""
    return await rag_search.get_raw_reviews(inp["movie_id"], limit=int(inp.get("limit") or 10))


RAG_HANDLERS = {
    "search_movie_summary": search_movie_summary,
    "search_aspect_evidence": search_aspect_evidence,
    "get_raw_reviews": get_raw_reviews,
}


def rag_disabled_error() -> dict:
    """Rag disabled error.

    Returns:
        (dict) Kết quả trả về."""
    return {"error": "RAG disabled"}


def is_rag_enabled() -> bool:
    """Is rag enabled.

    Returns:
        (bool) Kết quả trả về."""
    return RAG_ENABLED
