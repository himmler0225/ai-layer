from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from app.config.db.models import RawReview
from app.config.db.session import get_session_factory
from app.config.db.utils import model_to_dict


async def upsert_raw_reviews(rows: list[dict]) -> int:
    """Bulk insert or update raw reviews, keyed by id.

    On conflict, refreshes content, rating, likes, author, and metadata.

    Args:
        rows: Raw review dicts with "id", "movie_id", "source", "content"
            and optional "source_video_id", "author", "rating", "likes",
            "metadata".

    Returns:
        The number of rows submitted (0 if `rows` is empty).
    """
    if not rows:
        return 0
    factory = await get_session_factory()
    async with factory() as session:
        stmt = insert(RawReview).values(
            [
                {
                    "id": row["id"],
                    "movie_id": row["movie_id"],
                    "source": row["source"],
                    "source_video_id": row.get("source_video_id"),
                    "author": row.get("author", ""),
                    "content": row["content"],
                    "rating": row.get("rating"),
                    "likes": row.get("likes", 0),
                    "metadata_": row.get("metadata", {}),
                }
                for row in rows
            ]
        )
        excluded = stmt.excluded
        stmt = stmt.on_conflict_do_update(
            index_elements=[RawReview.id],
            set_={
                "content": excluded.content,
                "rating": excluded.rating,
                "likes": excluded.likes,
                "author": excluded.author,
                "metadata": excluded.metadata,
            },
        )
        await session.execute(stmt)
        await session.commit()
    return len(rows)


async def get_raw_reviews(movie_id: str, *, limit: int = 100, sort_by_likes: bool = True) -> list[dict]:
    """Fetch a movie's raw reviews.

    Args:
        movie_id: Movie id to filter by.
        limit: Maximum number of reviews to return.
        sort_by_likes: If True, order by likes descending; otherwise order
            by creation time descending.

    Returns:
        Raw review rows as dicts.
    """
    factory = await get_session_factory()
    async with factory() as session:
        q = select(RawReview).where(RawReview.movie_id == movie_id)
        if sort_by_likes:
            q = q.order_by(RawReview.likes.desc())
        else:
            q = q.order_by(RawReview.created_at.desc())
        q = q.limit(limit)
        rows = (await session.execute(q)).scalars().all()
        return [model_to_dict(row) for row in rows]


async def count_raw_reviews(movie_id: str) -> int:
    """Count how many raw reviews a movie has.

    Args:
        movie_id: Movie id to count reviews for.

    Returns:
        The number of raw reviews stored for the movie.
    """
    factory = await get_session_factory()
    async with factory() as session:
        return int(
            await session.scalar(select(func.count()).select_from(RawReview).where(RawReview.movie_id == movie_id)) or 0
        )
