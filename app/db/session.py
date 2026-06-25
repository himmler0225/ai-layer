"""PostgreSQL async session — SQLAlchemy + asyncpg."""

from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.config.settings as _s
from app.config.logger import Logger
from app.db.models import Base

logger = Logger.get(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _database_url() -> str:
    """Chuẩn hóa DATABASE_URL sang driver asyncpg."""
    url = _s.DATABASE_URL
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


async def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Khởi tạo engine và session factory lần đầu."""
    global _engine, _session_factory

    if _session_factory is None:
        _engine = create_async_engine(
            _database_url(),
            pool_size=5,
            max_overflow=15,
            json_serializer=json.dumps,
            json_deserializer=json.loads,
        )
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    return _session_factory


async def init_db() -> None:
    """Tạo bảng Postgres; bỏ video_chunks nếu không có pgvector."""
    await get_session_factory()
    assert _engine is not None

    async with _engine.begin() as conn:
        has_vector = False
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            has_vector = True
        except Exception as exc:
            logger.warning(
                "[db] pgvector unavailable (%s) — video_chunks table skipped; "
                "use pgvector/pgvector image or install pgvector on PostgreSQL",
                exc,
            )

        tables = list(Base.metadata.sorted_tables)
        if not has_vector:
            tables = [t for t in tables if t.name != "video_chunks"]

        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(sync_conn, tables=tables)
        )

    logger.info("[db] tables initialized vector=%s", has_vector)


async def close_engine() -> None:
    """Đóng connection pool Postgres."""
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None