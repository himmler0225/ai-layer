from __future__ import annotations

"""CRUD bảng videos."""


from typing import Optional

from sqlalchemy import exists, func, select, update
from sqlalchemy.dialects.postgresql import insert

from app.config.db.models import Video
from app.config.db.session import get_session_factory
from app.config.db.utils import model_to_dict


async def get_video(video_id: str) -> Optional[dict]:
    """Lấy một video từ Postgres theo id."""
    factory = await get_session_factory()
    async with factory() as session:
        row = await session.scalar(select(Video).where(Video.id == video_id))
        return model_to_dict(row) if row else None


async def exists_video(video_id: str) -> bool:
    """Kiểm tra video đã có trong DB chưa."""
    factory = await get_session_factory()
    async with factory() as session:
        return bool(await session.scalar(select(exists().where(Video.id == video_id))))


async def upsert_video(
    *,
    id: str,
    platform: str,
    title: str = "",
    author: str = "",
    views: int = 0,
    likes: int = 0,
    comments_count: int = 0,
    url: str = "",
    transcript: str = "",
    metadata: dict | None = None,
) -> None:
    """Insert hoặc merge metadata video."""
    factory = await get_session_factory()
    async with factory() as session:
        stmt = insert(Video).values(
            id=id,
            platform=platform,
            title=title,
            author=author,
            views=views,
            likes=likes,
            comments_count=comments_count,
            url=url,
            transcript=transcript,
            metadata_=metadata or {},
        )
        excluded = stmt.excluded
        stmt = stmt.on_conflict_do_update(
            index_elements=[Video.id],
            set_={
                "title": excluded.title,
                "author": excluded.author,
                "views": excluded.views,
                "likes": excluded.likes,
                "comments_count": excluded.comments_count,
                "url": excluded.url,
                "transcript": func.coalesce(
                    func.nullif(excluded.transcript, ""),
                    Video.transcript,
                ),
                "metadata": excluded.metadata,
                "updated_at": func.now(),
            },
        )
        await session.execute(stmt)
        await session.commit()


async def update_transcript(video_id: str, transcript: str) -> None:
    """Ghi đè nội dung transcript của video."""
    factory = await get_session_factory()
    async with factory() as session:
        await session.execute(
            update(Video)
            .where(Video.id == video_id)
            .values(transcript=transcript, updated_at=func.now())
        )
        await session.commit()
