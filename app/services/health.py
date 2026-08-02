import httpx

import app.config.settings as settings
from app.config.constants import HEALTH_CHECK_TIMEOUT
from app.config.defaults import load_schema
from app.config.loader import provider_settings_prefix, runtime


async def check_postgres() -> str:
    """Check postgres (async).

    Returns:
        (str) Kết quả trả về."""
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
    """Check redis (async).

    Returns:
        (str) Kết quả trả về."""
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
    """Check data miner (async).

    Returns:
        (str) Kết quả trả về."""
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
    """API key của provider đang active trong AI_MODELS."""
    active = (runtime.active_provider or "").strip()
    if not active:
        return "missing AI_MODELS.is_active"
    prefix = provider_settings_prefix(active, load_schema())
    val = getattr(settings, f"{prefix}_API_KEY", None)
    return "set" if str(val or "").strip() else "missing"


async def collect_checks() -> dict[str, str]:
    """Thu thập checks (async).

    Returns:
        (dict[str, str]) Kết quả trả về."""
    return {
        "postgres": await check_postgres(),
        "redis": await check_redis(),
        "data_miner": await check_data_miner(),
        "llm_key": check_llm_key(),
    }


def is_healthy(checks: dict[str, str]) -> bool:
    """Is healthy.

    Args:
        checks: (dict[str, str]) Tham số `checks`.

    Returns:
        (bool) Kết quả trả về."""
    if checks.get("postgres") != "ok":
        return False
    if checks.get("redis") != "ok":
        return False
    if checks.get("data_miner") != "ok":
        return False
    if checks.get("llm_key") != "set":
        return False
    return True
