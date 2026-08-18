from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from app.config.db.models import AspectSummary
from app.config.db.session import get_session_factory
from app.config.db.utils import model_to_dict
from app.repositories.pgvector import vector_literal


async def upsert_aspect_summary(
    *,
    id: str,
    movie_id: str,
    aspect: str,
    summary: str,
    pros: list | None = None,
    cons: list | None = None,
    positive_percent: float | None = None,
    source_chunk_ids: list | None = None,
    embedding: list[float] | None = None,
) -> None:
    """Insert or update the aspect summary for a movie+aspect pair.

    On conflict (same movie_id, aspect), refreshes summary, pros, cons,
    positive_percent, source_chunk_ids, embedding, and updated_at.

    Args:
        id: Primary key for the summary row.
        movie_id: Movie the summary belongs to.
        aspect: Aspect name (e.g. "acting", "plot").
        summary: Generated summary text.
        pros: Positive points extracted for this aspect.
        cons: Negative points extracted for this aspect.
        positive_percent: Share of reviews that were positive on this
            aspect, if computed.
        source_chunk_ids: Ids of the aspect chunks this summary was built
            from.
        embedding: Vector embedding of the summary, for similarity search.
    """
    factory = await get_session_factory()
    async with factory() as session:
        stmt = insert(AspectSummary).values(
            id=id,
            movie_id=movie_id,
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
            index_elements=[AspectSummary.movie_id, AspectSummary.aspect],
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


async def get_aspect_summaries(movie_id: str, *, aspect: str | None = None) -> list[dict]:
    """Fetch a movie's aspect summaries, ordered by aspect name.

    Args:
        movie_id: Movie id to filter by.
        aspect: If given, restrict results to this aspect only.

    Returns:
        Aspect summary rows as dicts.
    """
    factory = await get_session_factory()
    async with factory() as session:
        q = select(AspectSummary).where(AspectSummary.movie_id == movie_id)
        if aspect:
            q = q.where(AspectSummary.aspect == aspect)
        q = q.order_by(AspectSummary.aspect)
        rows = (await session.execute(q)).scalars().all()
        return [model_to_dict(row) for row in rows]


async def search_similar_summaries(
    movie_id: str, query_vector: list[float], *, aspect: str | None = None, limit: int = 8
) -> list[dict]:
    """Find aspect summaries for a movie whose embedding is closest to a query vector.

    Uses pgvector cosine distance (`<=>`) ordering, optionally restricted
    to a single aspect.

    Args:
        movie_id: Movie id to search within.
        query_vector: Query embedding to compare against.
        aspect: If given, restrict the search to this aspect only.
        limit: Maximum number of results to return.

    Returns:
        Rows with "aspect", "summary", "pros", "cons", "positive_percent",
        and a similarity "score" (1 - cosine distance), most similar first.
    """
    vec = vector_literal(query_vector)
    sql = text(
        "\n        SELECT aspect, summary, pros, cons, positive_percent,\n               1 - (embedding <=> CAST(:vec AS vector)) AS score\n        FROM aspect_summaries\n        WHERE movie_id = :pid\n          AND embedding IS NOT NULL\n          AND (CAST(:aspect AS text) IS NULL OR aspect = :aspect)\n        ORDER BY embedding <=> CAST(:vec AS vector)\n        LIMIT :k\n    "
    )
    factory = await get_session_factory()
    async with factory() as session:
        rows = (
            (await session.execute(sql, {"vec": vec, "pid": movie_id, "aspect": aspect, "k": limit})).mappings().all()
        )
        return [dict(r) for r in rows]
