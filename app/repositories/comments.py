from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from app.config.db.models import Comment
from app.config.db.session import get_session_factory
from app.config.db.utils import model_to_dict


async def insert_comments(video_id: str, comments: list[dict]) -> None:
    """Bulk insert comments for a video, skipping ids that already exist.

    Args:
        video_id: Video the comments belong to.
        comments: Comment dicts with "id" and optional "author", "content",
            "likes", "published_at", "metadata".
    """
    if not comments:
        return
    factory = await get_session_factory()
    async with factory() as session:
        stmt = insert(Comment).on_conflict_do_nothing(index_elements=[Comment.id])
        await session.execute(
            stmt,
            [
                {
                    "id": item["id"],
                    "video_id": video_id,
                    "author": item.get("author", ""),
                    "content": item.get("content", ""),
                    "likes": item.get("likes", 0),
                    "published_at": item.get("published_at"),
                    "metadata_": item.get("metadata", {}),
                }
                for item in comments
            ],
        )
        await session.commit()


async def get_comments(video_id: str, limit: int = 100) -> list[dict]:
    """Fetch a video's comments, most-liked first.

    Args:
        video_id: Video to fetch comments for.
        limit: Maximum number of comments to return.

    Returns:
        Comment rows as dicts.
    """
    factory = await get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Comment).where(Comment.video_id == video_id).order_by(Comment.likes.desc()).limit(limit)
        )
        return [model_to_dict(row) for row in result.scalars().all()]


async def count_comments(video_id: str) -> int:
    """Count how many comments a video has.

    Args:
        video_id: Video to count comments for.

    Returns:
        The number of comments stored for the video.
    """
    factory = await get_session_factory()
    async with factory() as session:
        return int(
            await session.scalar(select(func.count()).select_from(Comment).where(Comment.video_id == video_id)) or 0
        )


async def delete_comments(video_id: str) -> None:
    """Delete all comments for a video.

    Args:
        video_id: Video whose comments should be deleted.
    """
    factory = await get_session_factory()
    async with factory() as session:
        await session.execute(delete(Comment).where(Comment.video_id == video_id))
        await session.commit()
