from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from app.config.db.models import SearchCache
from app.config.db.session import get_session_factory

async def get_search_cache(query: str, platform: str) -> Optional[list[str]]:
    """Lấy search cache (async).

    Args:
        query: (str) Tham số `query`.
        platform: (str) Tham số `platform`.

    Returns:
        (Optional[list[str]]) Kết quả trả về."""
    factory = await get_session_factory()
    async with factory() as session:
        return await session.scalar(select(SearchCache.video_ids).where(SearchCache.query == query, SearchCache.platform == platform))

async def upsert_search_cache(query: str, platform: str, video_ids: list[str]) -> None:
    """Upsert search cache (async).

    Args:
        query: (str) Tham số `query`.
        platform: (str) Tham số `platform`.
        video_ids: (list[str]) Tham số `video_ids`.

    Returns:
        (None) Kết quả trả về."""
    factory = await get_session_factory()
    async with factory() as session:
        stmt = insert(SearchCache).values(query=query, platform=platform, video_ids=video_ids, updated_at=func.now())
        stmt = stmt.on_conflict_do_update(index_elements=[SearchCache.query, SearchCache.platform], set_={'video_ids': stmt.excluded.video_ids, 'updated_at': func.now()})
        await session.execute(stmt)
        await session.commit()

async def delete_search_cache(query: str, platform: str) -> None:
    """Delete search cache (async).

    Args:
        query: (str) Tham số `query`.
        platform: (str) Tham số `platform`.

    Returns:
        (None) Kết quả trả về."""
    factory = await get_session_factory()
    async with factory() as session:
        await session.execute(delete(SearchCache).where(SearchCache.query == query, SearchCache.platform == platform))
        await session.commit()

async def clear_expired_cache(days: int=7) -> None:
    """Clear expired cache (async).

    Args:
        days: (int, mặc định 7) Tham số `days`.

    Returns:
        (None) Kết quả trả về."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    factory = await get_session_factory()
    async with factory() as session:
        await session.execute(delete(SearchCache).where(SearchCache.updated_at < cutoff))
        await session.commit()
