from __future__ import annotations
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from app.config.db.models import RawReview
from app.config.db.session import get_session_factory
from app.config.db.utils import model_to_dict

async def upsert_raw_reviews(rows: list[dict]) -> int:
    """Upsert raw reviews (async).

    Args:
        rows: (list[dict]) Tham số `rows`.

    Returns:
        (int) Kết quả trả về."""
    if not rows:
        return 0
    factory = await get_session_factory()
    async with factory() as session:
        stmt = insert(RawReview).values([{'id': row['id'], 'product_id': row['product_id'], 'source': row['source'], 'source_video_id': row.get('source_video_id'), 'author': row.get('author', ''), 'content': row['content'], 'rating': row.get('rating'), 'likes': row.get('likes', 0), 'metadata_': row.get('metadata', {})} for row in rows])
        excluded = stmt.excluded
        stmt = stmt.on_conflict_do_update(index_elements=[RawReview.id], set_={'content': excluded.content, 'rating': excluded.rating, 'likes': excluded.likes, 'author': excluded.author, 'metadata': excluded.metadata})
        await session.execute(stmt)
        await session.commit()
    return len(rows)

async def get_raw_reviews(product_id: str, *, limit: int=100, sort_by_likes: bool=True) -> list[dict]:
    """Lấy raw reviews (async).

    Args:
        product_id: (str) Tham số `product_id`.
        limit: (int, mặc định 100) Tham số `limit`.
        sort_by_likes: (bool, mặc định True) Tham số `sort_by_likes`.

    Returns:
        (list[dict]) Kết quả trả về."""
    factory = await get_session_factory()
    async with factory() as session:
        q = select(RawReview).where(RawReview.product_id == product_id)
        if sort_by_likes:
            q = q.order_by(RawReview.likes.desc())
        else:
            q = q.order_by(RawReview.created_at.desc())
        q = q.limit(limit)
        rows = (await session.execute(q)).scalars().all()
        return [model_to_dict(row) for row in rows]

async def count_raw_reviews(product_id: str) -> int:
    """Count raw reviews (async).

    Args:
        product_id: (str) Tham số `product_id`.

    Returns:
        (int) Kết quả trả về."""
    factory = await get_session_factory()
    async with factory() as session:
        return int(await session.scalar(select(func.count()).select_from(RawReview).where(RawReview.product_id == product_id)) or 0)
