"""Health check các dependency của ai-layer."""

from __future__ import annotations

import httpx

import app.config.settings as settings
from app.config.constants import HEALTH_CHECK_TIMEOUT


async def check_postgres() -> str:
    """Ping Postgres qua SELECT 1."""
    if not settings.DATABASE_URL:
        return "missing DATABASE_URL"
    try:
        from sqlalchemy import text

        from app.db.session import get_session_factory

        factory = await get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:
        return f"error: {exc}"


async def check_redis() -> str:
    """Ping Redis."""
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
    """Ping RabbitMQ — skipped nếu ingest tắt hoặc chưa cấu hình URL."""
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
    """GET /health của data-miner."""
    try:
        async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT) as client:
            r = await client.get(f"{settings.DATA_MINER_URL}/health")
        return "ok" if r.is_success else f"status {r.status_code}"
    except Exception as exc:
        return f"unreachable: {exc}"


def check_openai_key() -> str:
    """Kiểm tra OPENAI_API_KEY đã load (thường từ Supabase config)."""
    return "set" if settings.OPENAI_API_KEY else "missing"


async def collect_checks() -> dict[str, str]:
    """Chạy tất cả check và trả map tên → trạng thái."""
    return {
        "postgres": await check_postgres(),
        "redis": await check_redis(),
        "rabbitmq": await check_rabbitmq(),
        "data_miner": await check_data_miner(),
        "openai_key": check_openai_key(),
    }


def is_healthy(checks: dict[str, str]) -> bool:
    """True khi các dependency bắt buộc đều ok."""
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
