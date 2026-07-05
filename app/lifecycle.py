"""Application startup and shutdown."""

import asyncio

import app.config.settings as settings
from app.config.logger import Logger
from app.exceptions import AiLayerConfigError

logger = Logger.get(__name__)

_ingest_worker_task: asyncio.Task | None = None
_config_refresh_task: asyncio.Task | None = None


async def _remote_config_refresher() -> None:
    from app.config.remote import load_and_apply

    while True:
        await asyncio.sleep(max(settings.REMOTE_CONFIG_TTL, 1) * 60)
        try:
            await load_and_apply()
            logger.info("[remote_config] refreshed")
        except Exception as exc:
            logger.warning("[remote_config] refresh failed: %s", exc)


async def _start_config_refresher() -> None:
    global _config_refresh_task
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        return
    _config_refresh_task = asyncio.create_task(_remote_config_refresher(), name="config-refresher")


async def _stop_config_refresher() -> None:
    global _config_refresh_task
    if _config_refresh_task is None:
        return
    _config_refresh_task.cancel()
    try:
        await _config_refresh_task
    except asyncio.CancelledError:
        pass
    _config_refresh_task = None


async def _start_inline_ingest_worker() -> None:
    global _ingest_worker_task
    from app.ingest.config import INGEST_ENABLED, INGEST_WORKER_INLINE, RABBITMQ_URL

    if not INGEST_ENABLED or not RABBITMQ_URL:
        return
    if not INGEST_WORKER_INLINE:
        logger.info("[startup] ingest worker inline disabled (INGEST_WORKER_INLINE=false)")
        return
    from app.ingest.consumer.worker import run_consumer

    _ingest_worker_task = asyncio.create_task(run_consumer(), name="ingest-worker")
    logger.info("[startup] ingest worker inline started")


async def _stop_inline_ingest_worker() -> None:
    global _ingest_worker_task
    if _ingest_worker_task is None:
        return
    _ingest_worker_task.cancel()
    try:
        await _ingest_worker_task
    except asyncio.CancelledError:
        pass
    _ingest_worker_task = None
    logger.info("[shutdown] ingest worker inline stopped")


def validate_startup_config() -> None:
    if not settings.API_KEYS:
        raise AiLayerConfigError("API_KEYS must be set before starting ai-layer")
    if not settings.DATA_MINER_URL or not settings.DATA_MINER_KEY:
        raise AiLayerConfigError("DATA_MINER_URL and DATA_MINER_KEY must be configured")
    if settings.APP_ENV != "development" and not settings.DATA_MINER_SERVICE_TOKEN:
        raise AiLayerConfigError("DATA_MINER_SERVICE_TOKEN must be configured")


async def startup() -> None:
    validate_startup_config()
    from app.cache.client import get_redis
    from app.config.db.session import init_db

    try:
        await init_db()
    except Exception as exc:
        logger.error("[db] init failed: %s", exc)
        raise AiLayerConfigError(f"Database initialization failed: {exc}", cause=exc) from exc
    await get_redis()
    await _start_config_refresher()
    from app.ingest.producer.publisher import init_producer

    await init_producer()
    await _start_inline_ingest_worker()
    from app.mcp.config import AGENT_CRAWL_BACKEND

    if AGENT_CRAWL_BACKEND == "mcp":
        from app.mcp.catalog import crawl_catalog

        try:
            loaded = await crawl_catalog.refresh()
            logger.info("[startup] MCP catalog ready tools=%d", len(loaded))
        except Exception as exc:
            logger.warning("[startup] MCP catalog preload failed (will retry on request): %s", exc)


async def shutdown() -> None:
    await _stop_inline_ingest_worker()
    await _stop_config_refresher()
    from app.cache.client import close_redis
    from app.clients.data_miner import close_client as close_dm
    from app.config.db.session import close_engine
    from app.ingest.producer.publisher import close_producer

    await close_producer()
    await close_dm()
    await close_engine()
    await close_redis()
