from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from app.config.db.models import Movie
from app.config.db.session import get_session_factory
from app.config.db.utils import model_to_dict


async def get_movie(movie_id: str) -> dict | None:
    factory = await get_session_factory()
    async with factory() as session:
        row = await session.scalar(select(Movie).where(Movie.id == movie_id))
        return model_to_dict(row) if row else None


async def exists_movie(movie_id: str) -> bool:
    factory = await get_session_factory()
    async with factory() as session:
        row = await session.scalar(select(Movie.id).where(Movie.id == movie_id))
        return row is not None


async def upsert_movie(*, id: str, name: str, platform: str = "mixed", metadata: dict | None = None) -> None:
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


async def list_movies(*, platform: str | None = None, limit: int = 50) -> list[dict]:
    factory = await get_session_factory()
    async with factory() as session:
        q = select(Movie).order_by(Movie.updated_at.desc()).limit(limit)
        if platform:
            q = q.where(Movie.platform == platform)
        rows = (await session.execute(q)).scalars().all()
        return [model_to_dict(row) for row in rows]
