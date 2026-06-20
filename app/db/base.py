from __future__ import annotations
import json
import asyncpg
import app.config.settings as _s
from app.config.logger import Logger

logger = Logger.get(__name__)

_pool: asyncpg.Pool | None = None


async def _init_conn(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
    await conn.set_type_codec("json",  encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        url = _s.DATABASE_URL
        if not url:
            raise RuntimeError("DATABASE_URL is not configured")
        _pool = await asyncpg.create_pool(url, init=_init_conn, min_size=2, max_size=10)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def init_tables() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
              id         TEXT        PRIMARY KEY,
              user_id    TEXT        NOT NULL,
              title      TEXT        NOT NULL DEFAULT 'New chat',
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
              id         TEXT        PRIMARY KEY,
              session_id TEXT        NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
              role       TEXT        NOT NULL CHECK (role IN ('user', 'assistant')),
              content    TEXT        NOT NULL DEFAULT '',
              metadata   JSONB,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS chat_sessions_user_updated
              ON chat_sessions (user_id, updated_at DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS chat_messages_session_created
              ON chat_messages (session_id, created_at ASC)
        """)
