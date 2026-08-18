from sqlalchemy.dialects.postgresql import insert
from app.config.db.models import Comment
from app.config.db.session import get_session_factory


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
