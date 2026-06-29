from __future__ import annotations
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from app.config.db.models import Comment
from app.config.db.session import get_session_factory
from app.config.db.utils import model_to_dict

async def insert_comments(video_id: str, comments: list[dict]) -> None:
    """Insert comments (async).

    Args:
        video_id: (str) Tham số `video_id`.
        comments: (list[dict]) Tham số `comments`.

    Returns:
        (None) Kết quả trả về."""
    if not comments:
        return
    factory = await get_session_factory()
    async with factory() as session:
        stmt = insert(Comment).on_conflict_do_nothing(index_elements=[Comment.id])
        await session.execute(stmt, [{'id': item['id'], 'video_id': video_id, 'author': item.get('author', ''), 'content': item.get('content', ''), 'likes': item.get('likes', 0), 'published_at': item.get('published_at'), 'metadata_': item.get('metadata', {})} for item in comments])
        await session.commit()

async def get_comments(video_id: str, limit: int=100) -> list[dict]:
    """Lấy comments (async).

    Args:
        video_id: (str) Tham số `video_id`.
        limit: (int, mặc định 100) Tham số `limit`.

    Returns:
        (list[dict]) Kết quả trả về."""
    factory = await get_session_factory()
    async with factory() as session:
        result = await session.execute(select(Comment).where(Comment.video_id == video_id).order_by(Comment.likes.desc()).limit(limit))
        return [model_to_dict(row) for row in result.scalars().all()]

async def count_comments(video_id: str) -> int:
    """Count comments (async).

    Args:
        video_id: (str) Tham số `video_id`.

    Returns:
        (int) Kết quả trả về."""
    factory = await get_session_factory()
    async with factory() as session:
        return int(await session.scalar(select(func.count()).select_from(Comment).where(Comment.video_id == video_id)) or 0)

async def delete_comments(video_id: str) -> None:
    """Delete comments (async).

    Args:
        video_id: (str) Tham số `video_id`.

    Returns:
        (None) Kết quả trả về."""
    factory = await get_session_factory()
    async with factory() as session:
        await session.execute(delete(Comment).where(Comment.video_id == video_id))
        await session.commit()
