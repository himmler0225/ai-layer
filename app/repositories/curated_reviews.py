from __future__ import annotations
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from app.config.db.models import CuratedReview
from app.config.db.session import get_session_factory
from app.config.db.utils import model_to_dict

async def replace_curated_reviews(movie_id: str, rows: list[dict]) -> int:
    """Replace curated reviews (async).

    Args:
        movie_id: (str) Tham số `movie_id`.
        rows: (list[dict]) Tham số `rows`.

    Returns:
        (int) Kết quả trả về."""
    factory = await get_session_factory()
    async with factory() as session:
        await session.execute(delete(CuratedReview).where(CuratedReview.movie_id == movie_id))
        if rows:
            await session.execute(insert(CuratedReview), [{'id': row['id'], 'movie_id': movie_id, 'raw_review_id': row['raw_review_id'], 'rank': row['rank'], 'likes': row.get('likes', 0), 'content': row['content']} for row in rows])
        await session.commit()
    return len(rows)

async def get_curated_reviews(movie_id: str, *, limit: int=300) -> list[dict]:
    """Lấy curated reviews (async).

    Args:
        movie_id: (str) Tham số `movie_id`.
        limit: (int, mặc định 300) Tham số `limit`.

    Returns:
        (list[dict]) Kết quả trả về."""
    factory = await get_session_factory()
    async with factory() as session:
        rows = (await session.execute(select(CuratedReview).where(CuratedReview.movie_id == movie_id).order_by(CuratedReview.rank).limit(limit))).scalars().all()
        return [model_to_dict(row) for row in rows]

async def count_curated_reviews(movie_id: str) -> int:
    """Count curated reviews (async).

    Args:
        movie_id: (str) Tham số `movie_id`.

    Returns:
        (int) Kết quả trả về."""
    factory = await get_session_factory()
    async with factory() as session:
        return len((await session.execute(select(CuratedReview.id).where(CuratedReview.movie_id == movie_id))).all())
