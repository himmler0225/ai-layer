from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from app.config.db.models import VideoChunk
from app.config.db.session import get_session_factory


async def upsert_chunks(rows: list[dict]) -> None:
    """Upsert chunks (async).

    Args:
        rows: (list[dict]) Tham số `rows`.

    Returns:
        (None) Kết quả trả về."""
    if not rows:
        return
    factory = await get_session_factory()
    async with factory() as session:
        stmt = insert(VideoChunk).values(
            [
                {
                    "id": row["id"],
                    "video_id": row["video_id"],
                    "platform": row["platform"],
                    "content": row["content"],
                    "embedding": row.get("embedding"),
                    "metadata_": row.get("metadata", {}),
                }
                for row in rows
            ]
        )
        excluded = stmt.excluded
        stmt = stmt.on_conflict_do_update(
            index_elements=[VideoChunk.id],
            set_={
                "content": excluded.content,
                "embedding": excluded.embedding,
                "metadata": excluded.metadata,
                "created_at": func.now(),
            },
        )
        await session.execute(stmt)
        await session.commit()
