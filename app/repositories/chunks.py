from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from app.db.models import VideoChunk
from app.db.session import get_session_factory


async def upsert_chunks(rows: list[dict]) -> None:
    """Ghi hoặc cập nhật vector chunk (pgvector)."""
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
