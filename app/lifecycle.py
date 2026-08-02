"""Application startup and shutdown."""

import asyncio

import app.config.settings as settings
from app.config.logger import Logger
from app.exceptions import AiLayerConfigError

logger = Logger.get(__name__)

_config_refresh_task: asyncio.Task | None = None


async def _remote_config_refresher() -> None:
    """(Nội bộ) Remote config refresher (async) `_remote_config_refresher`.

    Returns:
        (None) Kết quả trả về."""
    from app.config.remote import load_and_apply

    while True:
        await asyncio.sleep(max(settings.REMOTE_CONFIG_TTL, 1) * 60)
        try:
            await load_and_apply()
            logger.info("[remote_config] refreshed")
        except Exception as exc:
            logger.warning("[remote_config] refresh failed: %s", exc)


async def _start_config_refresher() -> None:
    """(Nội bộ) Bắt đầu config refresher (async) `_start_config_refresher`.

    Returns:
        (None) Kết quả trả về."""
    global _config_refresh_task
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        return
    _config_refresh_task = asyncio.create_task(_remote_config_refresher(), name="config-refresher")


async def _stop_config_refresher() -> None:
    """(Nội bộ) Dừng config refresher (async) `_stop_config_refresher`.

    Returns:
        (None) Kết quả trả về."""
    global _config_refresh_task
    if _config_refresh_task is None:
        return
    _config_refresh_task.cancel()
    try:
        await _config_refresh_task
    except asyncio.CancelledError:
        pass
    _config_refresh_task = None


def validate_startup_config() -> None:
    """Xác thực startup config.

    Returns:
        (None) Kết quả trả về."""
    if not settings.API_KEYS:
        raise AiLayerConfigError("API_KEYS must be set before starting ai-layer")
    if not settings.DATA_MINER_URL or not settings.DATA_MINER_KEY:
        raise AiLayerConfigError("DATA_MINER_URL and DATA_MINER_KEY must be configured")
    if settings.APP_ENV != "development" and not settings.DATA_MINER_SERVICE_TOKEN:
        raise AiLayerConfigError("DATA_MINER_SERVICE_TOKEN must be configured")


async def startup() -> None:
    """Startup (async).

    Returns:
        (None) Kết quả trả về."""
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
    from app.mcp.config import AGENT_CRAWL_BACKEND

    if AGENT_CRAWL_BACKEND == "mcp":
        from app.mcp.catalog import crawl_catalog

        try:
            loaded = await crawl_catalog.refresh()
            logger.info("[startup] MCP catalog ready tools=%d", len(loaded))
        except Exception as exc:
            logger.warning("[startup] MCP catalog preload failed (will retry on request): %s", exc)


async def shutdown() -> None:
    """Shutdown (async).

    Returns:
        (None) Kết quả trả về."""
    await _stop_config_refresher()
    from app.cache.client import close_redis
    from app.clients.data_miner import close_client as close_dm
    from app.config.db.session import close_engine

    await close_dm()
    await close_engine()
    await close_redis()
