import httpx

import app.config.settings as settings
from app.config.constants import HEALTH_CHECK_TIMEOUT
from app.config.defaults import load_schema
from app.config.loader import provider_settings_prefix, runtime


async def check_postgres() -> str:
    """Check Postgres connectivity by running a trivial `SELECT 1`.

    Returns:
        "missing DATABASE_URL" if unconfigured, "ok" on success, or
        "error: <exception>" if the query fails.
    """
    if not settings.DATABASE_URL:
        return "missing DATABASE_URL"
    try:
        from sqlalchemy import text

        from app.config.db.session import get_session_factory

        factory = await get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:
        return f"error: {exc}"


async def check_redis() -> str:
    """Check Redis connectivity via a `PING`.

    Returns:
        "unreachable" if no client could be obtained, "ok" on a successful
        ping, or "error: <exception>" if the ping fails.
    """
    try:
        from app.cache.client import get_redis

        redis = await get_redis()
        if redis is None:
            return "unreachable"
        await redis.ping()
        return "ok"
    except Exception as exc:
        return f"error: {exc}"


async def check_data_miner() -> str:
    """Check reachability of the external data-miner service via its `/health` endpoint.

    Returns:
        "missing DATA_MINER_URL" or "missing DATA_MINER_KEY" if unconfigured,
        "ok" on a successful response, "status <code>" for a non-success
        HTTP status, or "unreachable: <message>" on a request error.
    """
    if not settings.DATA_MINER_URL:
        return "missing DATA_MINER_URL"
    if not settings.DATA_MINER_KEY:
        return "missing DATA_MINER_KEY"
    try:
        async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT) as client:
            r = await client.get(f"{settings.DATA_MINER_URL.rstrip('/')}/health")
        if r.is_success:
            return "ok"
        return f"status {r.status_code}"
    except Exception as exc:
        msg = str(exc).strip() or type(exc).__name__
        return f"unreachable: {msg}"


def check_llm_key() -> str:
    """Check whether the API key for the currently active AI_MODELS provider is set.

    Returns:
        "missing AI_MODELS.is_active" if no provider is active, "set" if
        the corresponding `<PREFIX>_API_KEY` setting has a value, or
        "missing" otherwise.
    """
    active = (runtime.active_provider or "").strip()
    if not active:
        return "missing AI_MODELS.is_active"
    prefix = provider_settings_prefix(active, load_schema())
    val = getattr(settings, f"{prefix}_API_KEY", None)
    return "set" if str(val or "").strip() else "missing"


async def collect_checks() -> dict[str, str]:
    """Run all health checks and gather their results into a single dict.

    Returns:
        A dict with "postgres", "redis", "data_miner", and "llm_key" keys,
        each holding the corresponding check's status string.
    """
    return {
        "postgres": await check_postgres(),
        "redis": await check_redis(),
        "data_miner": await check_data_miner(),
        "llm_key": check_llm_key(),
    }


def is_healthy(checks: dict[str, str]) -> bool:
    """Decide overall system health from individual check results.

    Args:
        checks: Result dict from `collect_checks`, with "postgres", "redis",
            "data_miner", and "llm_key" status strings.

    Returns:
        True only if postgres, redis, and data_miner are all "ok" and
        llm_key is "set"; False otherwise.
    """
    if checks.get("postgres") != "ok":
        return False
    if checks.get("redis") != "ok":
        return False
    if checks.get("data_miner") != "ok":
        return False
    if checks.get("llm_key") != "set":
        return False
    return True
