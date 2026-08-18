from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from app.config.db.models import SearchCache
from app.config.db.session import get_session_factory


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
