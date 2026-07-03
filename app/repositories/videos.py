from sqlalchemy import exists, func, select, update
from sqlalchemy.dialects.postgresql import insert
from app.config.db.models import Video
from app.config.db.session import get_session_factory
from app.config.db.utils import model_to_dict


async def get_video(video_id: str) -> dict | None:
    """Lấy video (async).

    Args:
        video_id: (str) Tham số `video_id`.

    Returns:
        (Optional[dict]) Kết quả trả về."""
    factory = await get_session_factory()
    async with factory() as session:
        row = await session.scalar(select(Video).where(Video.id == video_id))
        return model_to_dict(row) if row else None


async def exists_video(video_id: str) -> bool:
    """Exists video (async).

    Args:
        video_id: (str) Tham số `video_id`.

    Returns:
        (bool) Kết quả trả về."""
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
    """Upsert video (async).

    Args:
        id: (str) Tham số `id`.
        platform: (str) Tham số `platform`.
        title: (str, mặc định '') Tham số `title`.
        author: (str, mặc định '') Tham số `author`.
        views: (int, mặc định 0) Tham số `views`.
        likes: (int, mặc định 0) Tham số `likes`.
        comments_count: (int, mặc định 0) Tham số `comments_count`.
        url: (str, mặc định '') Tham số `url`.
        transcript: (str, mặc định '') Tham số `transcript`.
        metadata: (dict | None, mặc định None) Tham số `metadata`.

    Returns:
        (None) Kết quả trả về."""
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
                "transcript": func.coalesce(func.nullif(excluded.transcript, ""), Video.transcript),
                "metadata": excluded.metadata,
                "updated_at": func.now(),
            },
        )
        await session.execute(stmt)
        await session.commit()


async def update_transcript(video_id: str, transcript: str) -> None:
    """Update transcript (async).

    Args:
        video_id: (str) Tham số `video_id`.
        transcript: (str) Tham số `transcript`.

    Returns:
        (None) Kết quả trả về."""
    factory = await get_session_factory()
    async with factory() as session:
        await session.execute(
            update(Video).where(Video.id == video_id).values(transcript=transcript, updated_at=func.now())
        )
        await session.commit()
