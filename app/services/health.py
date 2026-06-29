from __future__ import annotations

import httpx

import app.config.settings as settings
from app.config.constants import HEALTH_CHECK_TIMEOUT
from app.config.headers import get_data_miner_headers


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


async def check_rabbitmq() -> str:
    """Check rabbitmq (async).

    Returns:
        (str) Kết quả trả về."""
    if not settings.INGEST_ENABLED:
        return "skipped"
    if not settings.RABBITMQ_URL:
        return "missing RABBITMQ_URL"
    try:
        import aio_pika

        conn = await aio_pika.connect_robust(
            settings.RABBITMQ_URL,
            timeout=HEALTH_CHECK_TIMEOUT,
        )
        async with conn:
            channel = await conn.channel()
            await channel.close()
        return "ok"
    except Exception as exc:
        return f"error: {exc}"


async def check_data_miner() -> str:
    """Check data miner (async).

    Returns:
        (str) Kết quả trả về."""
    if not settings.DATA_MINER_KEY:
        return "missing DATA_MINER_KEY"
    try:
        async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT) as client:
            r = await client.get(
                f"{settings.DATA_MINER_URL}/api/videos/search",
                params={"q": "_health", "max_results": 1},
                headers=get_data_miner_headers(
                    settings.DATA_MINER_KEY,
                    settings.DATA_MINER_SERVICE_TOKEN,
                ),
            )
        if r.status_code == 401:
            return "auth: missing key"
        if r.status_code == 403:
            return "auth: invalid key or service token"
        return "ok" if r.is_success else f"status {r.status_code}"
    except Exception as exc:
        return f"unreachable: {exc}"


def check_openai_key() -> str:
    """Check openai key.

    Returns:
        (str) Kết quả trả về."""
    return "set" if settings.OPENAI_API_KEY else "missing"


async def collect_checks() -> dict[str, str]:
    """Thu thập checks (async).

    Returns:
        (dict[str, str]) Kết quả trả về."""
    return {
        "postgres": await check_postgres(),
        "redis": await check_redis(),
        "rabbitmq": await check_rabbitmq(),
        "data_miner": await check_data_miner(),
        "openai_key": check_openai_key(),
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
    if checks.get("openai_key") != "set":
        return False
    if settings.INGEST_ENABLED and checks.get("rabbitmq") != "ok":
        return False
    return True
