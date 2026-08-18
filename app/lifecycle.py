"""Application startup and shutdown."""

import asyncio

import app.config.settings as settings
from app.config.logger import Logger, log_event
from app.exceptions import AiLayerConfigError

logger = Logger.get(__name__)

_config_refresh_task: asyncio.Task | None = None


async def _remote_config_refresher() -> None:
    """Background loop that reloads and applies remote config on a fixed interval.

    Sleeps for REMOTE_CONFIG_TTL minutes (at least 1) between refreshes; logs
    and continues on failure instead of crashing the app."""
    from app.config.remote import load_and_apply

    while True:
        await asyncio.sleep(max(settings.REMOTE_CONFIG_TTL, 1) * 60)
        try:
            await load_and_apply()
            logger.info(log_event("remote_config", "refresh complete"))
        except Exception as exc:
            logger.warning(log_event("remote_config", "refresh failed", error=exc))


async def _start_config_refresher() -> None:
    """Start the background remote-config refresh task.

    No-op if Supabase credentials aren't configured, since remote config
    can't be loaded without them."""
    global _config_refresh_task
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        return
    _config_refresh_task = asyncio.create_task(_remote_config_refresher(), name="config-refresher")


async def _stop_config_refresher() -> None:
    """Cancel and await the background remote-config refresh task, if one is running."""
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
    """Validate that required settings are present before the app starts serving.

    Raises:
        AiLayerConfigError: if API_KEYS, DATA_MINER_URL/DATA_MINER_KEY are
            missing, or (outside development) DATA_MINER_SERVICE_TOKEN
            is missing."""
    if not settings.API_KEYS:
        raise AiLayerConfigError("API_KEYS must be set before starting ai-layer")
    if not settings.DATA_MINER_URL or not settings.DATA_MINER_KEY:
        raise AiLayerConfigError("DATA_MINER_URL and DATA_MINER_KEY must be configured")
    if settings.APP_ENV != "development" and not settings.DATA_MINER_SERVICE_TOKEN:
        raise AiLayerConfigError("DATA_MINER_SERVICE_TOKEN must be configured")


async def startup() -> None:
    """Run application startup: validate config, init the database and Redis,
    start the remote-config refresher, and preload the MCP tool catalog if
    the MCP crawl backend is enabled.

    Raises:
        AiLayerConfigError: if required settings are missing or database
            initialization fails."""
    validate_startup_config()
    from app.cache.client import get_redis
    from app.config.db.session import init_db

    try:
        await init_db()
    except Exception as exc:
        logger.error(log_event("db", "init failed", error=exc))
        raise AiLayerConfigError(f"Database initialization failed: {exc}", cause=exc) from exc
    await get_redis()
    await _start_config_refresher()
    from app.mcp.config import AGENT_CRAWL_BACKEND

    if AGENT_CRAWL_BACKEND == "mcp":
        from app.mcp.catalog import crawl_catalog

        try:
            loaded = await crawl_catalog.refresh()
            logger.info(log_event("startup", "mcp catalog ready", tools=len(loaded)))
        except Exception as exc:
            logger.warning(log_event("startup", "mcp catalog preload failed", error=exc, retry="on_request"))


async def shutdown() -> None:
    """Run application shutdown: stop the config refresher and close the
    data-miner client, movie-aggregator client, database engine, Redis
    connections, and flush any buffered Langfuse traces."""
    await _stop_config_refresher()
    from app.cache.client import close_redis
    from app.clients.data_miner import close_client as close_dm
    from app.clients.movie_aggregator import close_client as close_movie_aggregator
    from app.config.db.session import close_engine
    from app.config.langfuse import flush as flush_langfuse

    await close_dm()
    await close_movie_aggregator()
    await close_engine()
    await close_redis()
    flush_langfuse()
