from __future__ import annotations

"""CRUD cache search video_ids."""


from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from app.db.models import SearchCache
from app.db.session import get_session_factory


async def get_search_cache(query: str, platform: str) -> Optional[list[str]]:
    """Lấy danh sách video_id đã cache theo query."""
    factory = await get_session_factory()
    async with factory() as session:
        return await session.scalar(
            select(SearchCache.video_ids).where(
                SearchCache.query == query,
                SearchCache.platform == platform,
            )
        )


async def upsert_search_cache(
    query: str,
    platform: str,
    video_ids: list[str],
) -> None:
    """Lưu kết quả search (query → video_ids)."""
    factory = await get_session_factory()
    async with factory() as session:
        stmt = insert(SearchCache).values(
            query=query,
            platform=platform,
            video_ids=video_ids,
            updated_at=func.now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[SearchCache.query, SearchCache.platform],
            set_={
                "video_ids": stmt.excluded.video_ids,
                "updated_at": func.now(),
            },
        )
        await session.execute(stmt)
        await session.commit()


async def delete_search_cache(query: str, platform: str) -> None:
    """Xóa cache một cặp query/platform."""
    factory = await get_session_factory()
    async with factory() as session:
        await session.execute(
            delete(SearchCache).where(
                SearchCache.query == query,
                SearchCache.platform == platform,
            )
        )
        await session.commit()


async def clear_expired_cache(days: int = 7) -> None:
    """Dọn cache search cũ hơn N ngày."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    factory = await get_session_factory()
    async with factory() as session:
        await session.execute(
            delete(SearchCache).where(SearchCache.updated_at < cutoff)
        )
        await session.commit()
