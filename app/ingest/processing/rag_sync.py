import app.config.settings as settings
from app.config.logger import Logger, log_event
from app.ingest.mappers.social_review import map_social_raw_review, slugify_movie_id
from app.ingest.processing.curate import merge_curated
from app.ingest.producer.publisher import publish
from app.ingest.schemas import ROUTING_SUMMARIZE
from app.repositories.aspect_summaries import get_aspect_summaries
from app.repositories.curated_reviews import get_curated_reviews, replace_curated_reviews
from app.repositories.movies import get_movie, upsert_movie
from app.repositories.raw_reviews import count_raw_reviews, upsert_raw_reviews

logger = Logger.get(__name__)
_MIN_RAW_FOR_SUMMARIZE = 20
_RE_SUMMARIZE_DELTA = 50


async def _should_queue_summarize(movie_id: str, total_raw: int) -> bool:
    """Decide whether enough new raw reviews have accumulated to (re)trigger summarization.

    Requires at least `_MIN_RAW_FOR_SUMMARIZE` raw reviews. If the movie has no
    aspect summaries yet, summarization is always due; otherwise it's due once the
    raw review count has grown by at least `_RE_SUMMARIZE_DELTA` since the last run.

    Args:
        movie_id: Id of the movie to check.
        total_raw: Current total raw review count for the movie.

    Returns:
        True if a summarize job should be queued, False otherwise.
    """
    if total_raw < _MIN_RAW_FOR_SUMMARIZE:
        return False
    summaries = await get_aspect_summaries(movie_id)
    if not summaries:
        return True
    movie_row = await get_movie(movie_id)
    meta = (movie_row or {}).get("metadata") or {}
    last = int(meta.get("last_summarize_raw_count") or 0)
    return total_raw - last >= _RE_SUMMARIZE_DELTA


async def sync_comments_to_movie_rag(
    *, movie_hint: str, platform: str, video_id: str, raw_comments: list[dict]
) -> str | None:
    """Sync a batch of raw comments into the movie RAG pipeline and maybe queue a summarize job.

    Slugifies the movie hint into a movie id, upserts the movie row, maps and
    stores the raw comments as raw reviews, re-curates the top reviews for the
    movie, and publishes a summarize job if enough new raw reviews have
    accumulated since the last summarization.

    Args:
        movie_hint: Free-text movie/product hint; if blank, syncing is skipped.
        platform: Either "youtube" or "tiktok".
        video_id: Id of the video the comments were posted on.
        raw_comments: Raw comment payloads from the source API.

    Returns:
        The resolved movie id, or None if `movie_hint` is blank.
    """
    hint = (movie_hint or "").strip()
    if not hint:
        return None
    movie_id = slugify_movie_id(hint)
    existing = await get_movie(movie_id)
    meta = dict((existing or {}).get("metadata") or {})
    await upsert_movie(id=movie_id, name=hint, platform=platform, metadata=meta)
    rows: list[dict] = []
    for raw in raw_comments:
        row = map_social_raw_review(movie_id, platform, video_id, raw)
        if row:
            rows.append(row)
    if not rows:
        return movie_id
    await upsert_raw_reviews(rows)
    existing = await get_curated_reviews(movie_id, limit=getattr(settings, "AGENT_CURATED_TOP_N", 300))
    curated = merge_curated(existing, rows)
    await replace_curated_reviews(movie_id, curated)
    total = await count_raw_reviews(movie_id)
    if await _should_queue_summarize(movie_id, total):
        await publish(
            ROUTING_SUMMARIZE, platform=platform, video_id=movie_id, movie_hint=hint, payload={"movie_id": movie_id}
        )
        logger.info(log_event("rag_sync", "summarize queued", movie_id=movie_id, raw_reviews=total))
    return movie_id
