import json
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from app.exceptions import AiLayerConfigError
import app.config.settings as settings
from app.config.logger import Logger
from app.config.db.models import Base
from app.config.db.url import database_url_label, resolve_database_url

logger = Logger.get(__name__)
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _database_url() -> str:
    url = settings.DATABASE_URL
    if not url:
        raise AiLayerConfigError(
            "DATABASE_URL chưa cấu hình — lấy connection string từ Supabase Dashboard → Database"
        )
    async_url, _ = resolve_database_url(url)
    return async_url


def _connect_args() -> dict:
    if not settings.DATABASE_URL:
        return {}
    _, connect_args = resolve_database_url(settings.DATABASE_URL)
    return connect_args


async def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Lấy session factory (async).

    Returns:
        (async_sessionmaker[AsyncSession]) Kết quả trả về."""
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
    assert _engine is not None
    label = database_url_label(settings.DATABASE_URL)
    try:
        async with _engine.connect() as conn:
            version = (await conn.execute(text("SELECT version()"))).scalar_one()
            version_short = str(version).split(",")[0].strip()
        logger.info("[db] connected %s (%s)", label, version_short)
    except Exception as exc:
        logger.error("[db] connection failed %s: %s", label, exc)
        raise


async def init_db() -> None:
    """Khởi tạo db (async).

    Returns:
        (None) Kết quả trả về."""
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
                "[db] pgvector unavailable (%s) - video_chunks table skipped; enable extension on Supabase (config/supabase-setup.sql)",
                exc,
            )
        tables = list(Base.metadata.sorted_tables)
        if not has_vector:
            tables = [t for t in tables if t.name != "video_chunks"]
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=tables))
    logger.info("[db] tables initialized vector=%s", has_vector)


async def close_engine() -> None:
    """Đóng engine (async).

    Returns:
        (None) Kết quả trả về."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
