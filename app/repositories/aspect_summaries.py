from __future__ import annotations

"""CRUD bảng aspect_summaries (L1)."""


from typing import Optional

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert

from app.db.models import AspectSummary
from app.db.session import get_session_factory
from app.db.utils import model_to_dict
from app.repositories.pgvector import vector_literal


async def upsert_aspect_summary(
    *,
    id: str,
    product_id: str,
    aspect: str,
    summary: str,
    pros: list | None = None,
    cons: list | None = None,
    positive_percent: float | None = None,
    source_chunk_ids: list | None = None,
    embedding: list[float] | None = None,
) -> None:
    """Ghi hoặc cập nhật summary một aspect."""
    factory = await get_session_factory()
    async with factory() as session:
        stmt = insert(AspectSummary).values(
            id=id,
            product_id=product_id,
            aspect=aspect,
            summary=summary,
            pros=pros or [],
            cons=cons or [],
            positive_percent=positive_percent,
            source_chunk_ids=source_chunk_ids or [],
            embedding=embedding,
        )
        excluded = stmt.excluded
        stmt = stmt.on_conflict_do_update(
            index_elements=[AspectSummary.product_id, AspectSummary.aspect],
            set_={
                "summary": excluded.summary,
                "pros": excluded.pros,
                "cons": excluded.cons,
                "positive_percent": excluded.positive_percent,
                "source_chunk_ids": excluded.source_chunk_ids,
                "embedding": excluded.embedding,
                "updated_at": func.now(),
            },
        )
        await session.execute(stmt)
        await session.commit()


async def get_aspect_summaries(
    product_id: str,
    *,
    aspect: str | None = None,
) -> list[dict]:
    """Lấy summaries của sản phẩm."""
    factory = await get_session_factory()
    async with factory() as session:
        q = select(AspectSummary).where(AspectSummary.product_id == product_id)
        if aspect:
            q = q.where(AspectSummary.aspect == aspect)
        q = q.order_by(AspectSummary.aspect)
        rows = (await session.execute(q)).scalars().all()
        return [model_to_dict(row) for row in rows]


async def get_aspect_summary(product_id: str, aspect: str) -> Optional[dict]:
    """Lấy summary một aspect."""
    factory = await get_session_factory()
    async with factory() as session:
        row = await session.scalar(
            select(AspectSummary).where(
                AspectSummary.product_id == product_id,
                AspectSummary.aspect == aspect,
            )
        )
        return model_to_dict(row) if row else None


async def search_similar_summaries(
    product_id: str,
    query_vector: list[float],
    *,
    aspect: str | None = None,
    limit: int = 8,
) -> list[dict]:
    """Vector cosine search trên aspect_summaries (L1)."""
    vec = vector_literal(query_vector)
    sql = text(
        """
        SELECT aspect, summary, pros, cons, positive_percent,
               1 - (embedding <=> CAST(:vec AS vector)) AS score
        FROM aspect_summaries
        WHERE product_id = :pid
          AND embedding IS NOT NULL
          AND (CAST(:aspect AS text) IS NULL OR aspect = :aspect)
        ORDER BY embedding <=> CAST(:vec AS vector)
        LIMIT :k
    """
    )
    factory = await get_session_factory()
    async with factory() as session:
        rows = (
            (
                await session.execute(
                    sql, {"vec": vec, "pid": product_id, "aspect": aspect, "k": limit}
                )
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]
