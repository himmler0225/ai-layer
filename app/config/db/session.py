import json
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from app.exceptions import AiLayerConfigError
import app.config.settings as settings
from app.config.logger import Logger, log_event
from app.config.db.models import Base
from app.config.db.url import database_url_label, resolve_database_url

logger = Logger.get(__name__)
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _database_url() -> str:
    """Resolve and validate the configured database URL for async SQLAlchemy.

    Returns:
        str: The async-compatible database connection URL.

    Raises:
        AiLayerConfigError: If `DATABASE_URL` is not configured.
    """
    url = settings.DATABASE_URL
    if not url:
        raise AiLayerConfigError(
            "DATABASE_URL chưa cấu hình — lấy connection string từ Supabase Dashboard → Database"
        )
    async_url, _ = resolve_database_url(url)
    return async_url


def _connect_args() -> dict:
    """Build the asyncpg connect_args (SSL/pgbouncer settings) for the configured database URL.

    Returns:
        dict: Connect args to pass to `create_async_engine`, or empty if no URL is configured.
    """
    if not settings.DATABASE_URL:
        return {}
    _, connect_args = resolve_database_url(settings.DATABASE_URL)
    return connect_args


async def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the process-wide async session factory, creating the engine on first call.

    Returns:
        async_sessionmaker[AsyncSession]: The shared session factory.
    """
    global _engine, _session_factory
    if _session_factory is None:
        _engine = create_async_engine(
            _database_url(),
            pool_size=5,
            max_overflow=15,
            connect_args=_connect_args(),
            json_serializer=json.dumps,
            json_deserializer=json.loads,
        )
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _session_factory


async def _verify_connection() -> None:
    """Ping the database to confirm connectivity and log the server version.

    Raises:
        Exception: Re-raises any error encountered while connecting, after logging it.
    """
    assert _engine is not None
    label = database_url_label(settings.DATABASE_URL)
    try:
        async with _engine.connect() as conn:
            version = (await conn.execute(text("SELECT version()"))).scalar_one()
            version_short = str(version).split(",")[0].strip()
        logger.info(log_event("db", "connected", label=label, version=version_short))
    except Exception as exc:
        logger.error(log_event("db", "connection failed", label=label, error=exc))
        raise


async def init_db() -> None:
    """Initialize the database: create the session factory, verify connectivity,
    and create any missing tables.

    Enables the pgvector extension when available; if it isn't, the
    `video_chunks` table (which depends on pgvector) is skipped.
    """
    await get_session_factory()
    assert _engine is not None
    await _verify_connection()
    async with _engine.begin() as conn:
        has_vector = False
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            has_vector = True
        except Exception as exc:
            logger.warning(
                log_event(
                    "db",
                    "pgvector unavailable",
                    error=exc,
                    action="video_chunks_table_skipped",
                    hint="enable extension via config/supabase-setup.sql",
                )
            )
        tables = list(Base.metadata.sorted_tables)
        if not has_vector:
            tables = [t for t in tables if t.name != "video_chunks"]
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=tables))
    logger.info(log_event("db", "tables initialized", vector=has_vector))


async def close_engine() -> None:
    """Dispose of the shared async engine and reset the session factory."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
