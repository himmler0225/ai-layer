from __future__ import annotations
import redis.asyncio as aioredis
from app.config.settings import REDIS_HOST, REDIS_PORT, REDIS_DB

_redis: aioredis.Redis | None = None

async def get_redis() -> aioredis.Redis | None:
    global _redis
    if _redis is None:
        try:
            r = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
            await r.ping()
            _redis = r
        except Exception:
            _redis = None
    return _redis

async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
