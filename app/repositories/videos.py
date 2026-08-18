from sqlalchemy import exists, func, select, update
from sqlalchemy.dialects.postgresql import insert
from app.config.db.models import Video
from app.config.db.session import get_session_factory


async def exists_video(video_id: str) -> bool:
    """Check whether a video with the given id exists.

    Args:
        video_id: The video id to check.

    Returns:
        True if a video with that id exists.
    """
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
    """Insert a video, or update its stats/metadata if it already exists.

    On conflict, refreshes title, author, views, likes, comments_count,
    url, and metadata. The transcript is only overwritten if the new value
    is non-empty (`COALESCE(NULLIF(new, ''), old)`), so a blank transcript
    passed on a later upsert won't erase a previously stored one.

    Args:
        id: The video's id.
        platform: Source platform (e.g. "youtube", "tiktok").
        title: Video title.
        author: Video author/channel name.
        views: View count.
        likes: Like count.
        comments_count: Number of comments.
        url: Video URL.
        transcript: Video transcript text, if available.
        metadata: Extra metadata to store as JSON.
    """
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
    """Overwrite a video's stored transcript.

    Args:
        video_id: Video to update.
        transcript: New transcript text.
    """
    factory = await get_session_factory()
    async with factory() as session:
        await session.execute(
            update(Video).where(Video.id == video_id).values(transcript=transcript, updated_at=func.now())
        )
        await session.commit()
