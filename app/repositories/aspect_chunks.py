from __future__ import annotations
from typing import Optional
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from app.config.db.models import AspectChunk
from app.config.db.session import get_session_factory
from app.config.db.utils import model_to_dict
from app.repositories.pgvector import vector_literal

async def upsert_aspect_chunks(rows: list[dict]) -> int:
    if not rows:
        return 0
    factory = await get_session_factory()
    async with factory() as session:
        stmt = insert(AspectChunk).values([{'id': row['id'], 'product_id': row['product_id'], 'aspect': row['aspect'], 'content': row['content'], 'review_ids': row.get('review_ids', []), 'positive_percent': row.get('positive_percent'), 'negative_percent': row.get('negative_percent'), 'embedding': row.get('embedding'), 'metadata_': row.get('metadata', {})} for row in rows])
        excluded = stmt.excluded
        stmt = stmt.on_conflict_do_update(index_elements=[AspectChunk.id], set_={'content': excluded.content, 'review_ids': excluded.review_ids, 'positive_percent': excluded.positive_percent, 'negative_percent': excluded.negative_percent, 'embedding': excluded.embedding, 'metadata': excluded.metadata, 'created_at': func.now()})
        await session.execute(stmt)
        await session.commit()
    return len(rows)

async def get_aspect_chunks(product_id: str, *, aspect: str | None=None, limit: int=50) -> list[dict]:
    factory = await get_session_factory()
    async with factory() as session:
        q = select(AspectChunk).where(AspectChunk.product_id == product_id)
        if aspect:
            q = q.where(AspectChunk.aspect == aspect)
        q = q.order_by(AspectChunk.created_at.desc()).limit(limit)
        rows = (await session.execute(q)).scalars().all()
        return [model_to_dict(row) for row in rows]

async def get_aspect_chunk(chunk_id: str) -> Optional[dict]:
    factory = await get_session_factory()
    async with factory() as session:
        row = await session.scalar(select(AspectChunk).where(AspectChunk.id == chunk_id))
        return model_to_dict(row) if row else None

async def delete_aspect_chunks_for_product(product_id: str, *, keep_aspects: list[str]) -> int:
    factory = await get_session_factory()
    async with factory() as session:
        q = delete(AspectChunk).where(AspectChunk.product_id == product_id)
        if keep_aspects:
            q = q.where(AspectChunk.aspect.notin_(keep_aspects))
        result = await session.execute(q)
        await session.commit()
        return result.rowcount or 0

async def search_similar_chunks(product_id: str, query_vector: list[float], *, aspect: str | None=None, limit: int=8) -> list[dict]:
    vec = vector_literal(query_vector)
    sql = text('\n        SELECT aspect, content, review_ids, positive_percent,\n               1 - (embedding <=> CAST(:vec AS vector)) AS score\n        FROM aspect_chunks\n        WHERE product_id = :pid\n          AND embedding IS NOT NULL\n          AND (CAST(:aspect AS text) IS NULL OR aspect = :aspect)\n        ORDER BY embedding <=> CAST(:vec AS vector)\n        LIMIT :k\n    ')
    factory = await get_session_factory()
    async with factory() as session:
        rows = (await session.execute(sql, {'vec': vec, 'pid': product_id, 'aspect': aspect, 'k': limit})).mappings().all()
        return [dict(r) for r in rows]
