from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from app.config.db.models import Movie
from app.config.db.session import get_session_factory
from app.config.db.utils import model_to_dict


async def get_movie(movie_id: str) -> dict | None:
    """Fetch a single movie by id.

    Args:
        movie_id: The movie's id.

    Returns:
        The movie as a dict, or None if not found.
    """
    factory = await get_session_factory()
    async with factory() as session:
        row = await session.scalar(select(Movie).where(Movie.id == movie_id))
        return model_to_dict(row) if row else None


async def exists_movie(movie_id: str) -> bool:
    """Check whether a movie with the given id exists.

    Args:
        movie_id: The movie id to check.

    Returns:
        True if a movie with that id exists.
    """
    factory = await get_session_factory()
    async with factory() as session:
        row = await session.scalar(select(Movie.id).where(Movie.id == movie_id))
        return row is not None


async def upsert_movie(*, id: str, name: str, platform: str = "mixed", metadata: dict | None = None) -> None:
    """Insert a movie, or update its name/platform/metadata if it already exists.

    Args:
        id: The movie's id.
        name: Movie/product name.
        platform: Source platform the movie's data was aggregated from
            (defaults to "mixed" for multi-source movies).
        metadata: Extra metadata to store as JSON.
    """
    factory = await get_session_factory()
    async with factory() as session:
        stmt = insert(Movie).values(id=id, name=name, platform=platform, metadata_=metadata or {})
        excluded = stmt.excluded
        stmt = stmt.on_conflict_do_update(
            index_elements=[Movie.id],
            set_={
                "name": excluded.name,
                "platform": excluded.platform,
                "metadata": excluded.metadata,
                "updated_at": func.now(),
            },
        )
        await session.execute(stmt)
        await session.commit()
