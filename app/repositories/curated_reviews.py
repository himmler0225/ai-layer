from __future__ import annotations

"""CRUD bảng curated_reviews."""


from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.config.db.models import CuratedReview
from app.config.db.session import get_session_factory
from app.config.db.utils import model_to_dict


async def replace_curated_reviews(product_id: str, rows: list[dict]) -> int:
    """Thay toàn bộ curated của product (sau job curate)."""
    factory = await get_session_factory()
    async with factory() as session:
        await session.execute(
            delete(CuratedReview).where(CuratedReview.product_id == product_id)
        )
        if rows:
            await session.execute(
                insert(CuratedReview),
                [
                    {
                        "id": row["id"],
                        "product_id": product_id,
                        "raw_review_id": row["raw_review_id"],
                        "rank": row["rank"],
                        "likes": row.get("likes", 0),
                        "content": row["content"],
                    }
                    for row in rows
                ],
            )
        await session.commit()
    return len(rows)


async def get_curated_reviews(product_id: str, *, limit: int = 300) -> list[dict]:
    """Lấy curated reviews theo rank."""
    factory = await get_session_factory()
    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(CuratedReview)
                    .where(CuratedReview.product_id == product_id)
                    .order_by(CuratedReview.rank)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return [model_to_dict(row) for row in rows]


async def count_curated_reviews(product_id: str) -> int:
    """Đếm curated reviews."""
    factory = await get_session_factory()
    async with factory() as session:
        return len(
            (
                await session.execute(
                    select(CuratedReview.id).where(
                        CuratedReview.product_id == product_id
                    )
                )
            ).all()
        )
