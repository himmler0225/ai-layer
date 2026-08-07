from app.rag.config import RAG_MIN_SCORE, RAG_TOP_K
from app.ingest.processing.embeddings import embed_texts
from app.repositories.aspect_chunks import search_similar_chunks
from app.repositories.aspect_summaries import search_similar_summaries
from app.repositories.raw_reviews import get_raw_reviews as repo_get_raw_reviews


def _coverage(score: float, has_items: bool) -> str:
    """Classify how well the search results cover the query.

    Args:
        score: Similarity score of the best-matching item.
        has_items: Whether any items were found at all.

    Returns:
        "none" if there are no items, "sufficient" if the best score meets
        `RAG_MIN_SCORE`, otherwise "partial".
    """
    if not has_items:
        return "none"
    if score >= RAG_MIN_SCORE:
        return "sufficient"
    return "partial"


async def search_aspect_summary(
    movie_id: str, query: str, *, aspect: str | None = None, top_k: int | None = None
) -> dict:
    """Embed the query and search for the most similar aspect summaries of a movie.

    Args:
        movie_id: Movie slug to search within.
        query: Natural-language query to embed and match against.
        aspect: Optional aspect filter (e.g. "acting", "plot").
        top_k: Max number of results to return; defaults to `RAG_TOP_K`.

    Returns:
        A dict with "coverage" ("none"/"partial"/"sufficient") and "items"
        (the matched summary rows).
    """
    k = top_k or RAG_TOP_K
    query_vector = (await embed_texts([query]))[0]
    items = await search_similar_summaries(movie_id, query_vector, aspect=aspect, limit=k)
    best = float(items[0]["score"]) if items else 0.0
    return {"coverage": _coverage(best, bool(items)), "items": items}


async def search_aspect_evidence(
    movie_id: str, query: str, *, aspect: str | None = None, top_k: int | None = None
) -> dict:
    """Embed the query and search for the most similar aspect evidence chunks of a movie.

    Args:
        movie_id: Movie slug to search within.
        query: Natural-language query to embed and match against.
        aspect: Optional aspect filter (e.g. "acting", "plot").
        top_k: Max number of results to return; defaults to `RAG_TOP_K`.

    Returns:
        A dict with "coverage" ("none"/"partial"/"sufficient") and "items"
        (the matched evidence chunks).
    """
    k = top_k or RAG_TOP_K
    query_vector = (await embed_texts([query]))[0]
    items = await search_similar_chunks(movie_id, query_vector, aspect=aspect, limit=k)
    best = float(items[0]["score"]) if items else 0.0
    return {"coverage": _coverage(best, bool(items)), "items": items}


async def get_raw_reviews(movie_id: str, *, limit: int = 10) -> dict:
    """Fetch raw (unsummarized) reviews for a movie from the repository.

    Args:
        movie_id: Movie slug to fetch reviews for.
        limit: Maximum number of reviews to return.

    Returns:
        A dict with "coverage" ("sufficient" if any items found, else
        "none") and "items" (the raw review rows).
    """
    items = await repo_get_raw_reviews(movie_id, limit=limit)
    return {"coverage": "sufficient" if items else "none", "items": items}
