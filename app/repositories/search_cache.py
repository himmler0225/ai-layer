from datetime import datetime, timedelta, UTC
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from app.config.db.models import SearchCache
from app.config.db.session import get_session_factory


async def get_search_cache(query: str, platform: str) -> list[str] | None:
    """Look up cached video ids for a search query on a platform.

    Args:
        query: The search query string.
        platform: Platform the search was run against (e.g. "youtube").

    Returns:
        The cached list of video ids, or None if there's no cache entry.
    """
    factory = await get_session_factory()
    async with factory() as session:
        return await session.scalar(
            select(SearchCache.video_ids).where(SearchCache.query == query, SearchCache.platform == platform)
        )


async def upsert_search_cache(query: str, platform: str, video_ids: list[str]) -> None:
    """Store (or refresh) the cached search results for a query+platform pair.

    Args:
        query: The search query string.
        platform: Platform the search was run against.
        video_ids: Video ids returned by the search, to cache.
    """
    factory = await get_session_factory()
    async with factory() as session:
        stmt = insert(SearchCache).values(query=query, platform=platform, video_ids=video_ids, updated_at=func.now())
        stmt = stmt.on_conflict_do_update(
            index_elements=[SearchCache.query, SearchCache.platform],
            set_={"video_ids": stmt.excluded.video_ids, "updated_at": func.now()},
        )
        await session.execute(stmt)
        await session.commit()


async def delete_search_cache(query: str, platform: str) -> None:
    """Delete the cached search results for a query+platform pair.

    Args:
        query: The search query string.
        platform: Platform the search was run against.
    """
    factory = await get_session_factory()
    async with factory() as session:
        await session.execute(delete(SearchCache).where(SearchCache.query == query, SearchCache.platform == platform))
        await session.commit()


async def clear_expired_cache(days: int = 7) -> None:
    """Delete search cache entries older than a given age.

    Args:
        days: Age threshold in days; entries not updated within this many
            days are deleted.
    """
    cutoff = datetime.now(UTC) - timedelta(days=days)
    factory = await get_session_factory()
    async with factory() as session:
        await session.execute(delete(SearchCache).where(SearchCache.updated_at < cutoff))
        await session.commit()
