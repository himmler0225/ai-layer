from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from app.config.db.models import CuratedReview
from app.config.db.session import get_session_factory
from app.config.db.utils import model_to_dict


async def replace_curated_reviews(movie_id: str, rows: list[dict]) -> int:
    """Replace a movie's curated reviews with a new ranked set.

    Deletes all existing curated reviews for the movie, then bulk-inserts
    `rows` (both steps in the same transaction).

    Args:
        movie_id: Movie whose curated reviews should be replaced.
        rows: New curated review dicts with "id", "raw_review_id", "rank",
            "content", and optional "likes".

    Returns:
        The number of rows inserted.
    """
    factory = await get_session_factory()
    async with factory() as session:
        await session.execute(delete(CuratedReview).where(CuratedReview.movie_id == movie_id))
        if rows:
            await session.execute(
                insert(CuratedReview),
                [
                    {
                        "id": row["id"],
                        "movie_id": movie_id,
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


async def get_curated_reviews(movie_id: str, *, limit: int = 300) -> list[dict]:
    """Fetch a movie's curated reviews, ordered by rank.

    Args:
        movie_id: Movie id to filter by.
        limit: Maximum number of reviews to return.

    Returns:
        Curated review rows as dicts.
    """
    factory = await get_session_factory()
    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(CuratedReview)
                    .where(CuratedReview.movie_id == movie_id)
                    .order_by(CuratedReview.rank)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return [model_to_dict(row) for row in rows]


async def count_curated_reviews(movie_id: str) -> int:
    """Count how many curated reviews a movie has.

    Args:
        movie_id: Movie id to count reviews for.

    Returns:
        The number of curated reviews stored for the movie.
    """
    factory = await get_session_factory()
    async with factory() as session:
        return len((await session.execute(select(CuratedReview.id).where(CuratedReview.movie_id == movie_id))).all())
