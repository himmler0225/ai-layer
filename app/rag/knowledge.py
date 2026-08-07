from datetime import datetime, timedelta, UTC
import app.config.settings as settings
from app.repositories.aspect_summaries import get_aspect_summaries
from app.repositories.curated_reviews import count_curated_reviews
from app.repositories.movies import exists_movie


async def movie_has_knowledge(movie_id: str) -> bool:
    """Check whether a movie has enough ingested data to answer from RAG.

    True if the movie exists and either has aspect summaries or at least
    20 curated reviews.

    Args:
        movie_id: Movie slug to check.

    Returns:
        Whether the movie has sufficient knowledge for RAG search.
    """
    if not movie_id or not await exists_movie(movie_id):
        return False
    summaries = await get_aspect_summaries(movie_id)
    if summaries:
        return True
    return await count_curated_reviews(movie_id) >= 20


async def is_movie_fresh(movie_id: str, days: int | None = None) -> bool:
    """Check whether a movie's ingested aspect summaries are still within TTL.

    A movie is considered fresh if it has no `updated_at` timestamp (treated
    as always fresh) or if any summary was updated within the last `days`.

    Args:
        movie_id: Movie slug to check.
        days: TTL window in days; defaults to `settings.CACHE_TTL_DAYS` when omitted.

    Returns:
        Whether the movie's cached knowledge is still fresh.
    """
    ttl_days = days if days is not None else settings.CACHE_TTL_DAYS
    summaries = await get_aspect_summaries(movie_id)
    if not summaries:
        return False
    cutoff = datetime.now(UTC) - timedelta(days=ttl_days)
    for row in summaries:
        updated = row.get("updated_at")
        if updated is None:
            return True
        if isinstance(updated, datetime):
            ts = updated if updated.tzinfo else updated.replace(tzinfo=UTC)
            if ts >= cutoff:
                return True
    return False
