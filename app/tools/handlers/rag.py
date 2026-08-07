from typing import Any

from app.rag import search as rag_search
from app.rag.config import RAG_ENABLED


async def search_movie_summary(inp: dict) -> Any:
    """Tool handler: search aspect summaries for a movie (L1 RAG lookup).

    Args:
        inp: Tool input dict with "movie_id", "query", and optional "aspect".

    Returns:
        The result of `rag_search.search_aspect_summary`.
    """
    return await rag_search.search_aspect_summary(
        inp["movie_id"], inp["query"], aspect=inp.get("aspect")
    )


async def search_aspect_evidence(inp: dict) -> Any:
    """Tool handler: search aspect evidence chunks for a movie (L2 RAG lookup).

    Args:
        inp: Tool input dict with "movie_id", "query", and optional "aspect".

    Returns:
        The result of `rag_search.search_aspect_evidence`.
    """
    return await rag_search.search_aspect_evidence(
        inp["movie_id"], inp["query"], aspect=inp.get("aspect")
    )


async def get_raw_reviews(inp: dict) -> Any:
    """Tool handler: fetch raw reviews for a movie (L3 RAG lookup).

    Args:
        inp: Tool input dict with "movie_id" and optional "limit" (defaults to 10).

    Returns:
        The result of `rag_search.get_raw_reviews`.
    """
    return await rag_search.get_raw_reviews(inp["movie_id"], limit=int(inp.get("limit") or 10))


RAG_HANDLERS = {
    "search_movie_summary": search_movie_summary,
    "search_aspect_evidence": search_aspect_evidence,
    "get_raw_reviews": get_raw_reviews,
}


def rag_disabled_error() -> dict:
    """Build the standard error payload returned when a RAG tool is called while RAG is disabled.

    Returns:
        An {"error": "RAG disabled"} dict.
    """
    return {"error": "RAG disabled"}


def is_rag_enabled() -> bool:
    """Check whether the RAG feature flag is currently enabled.

    Returns:
        The current value of `RAG_ENABLED`.
    """
    return RAG_ENABLED
