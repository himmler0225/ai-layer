from __future__ import annotations

"""Xác thực JWT Supabase → user_id."""

import hashlib
import httpx
from fastapi import HTTPException
from app.config.settings import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_TOKEN_TTL
from app.cache.client import get_redis
from app.constants import SUPABASE_AUTH_TIMEOUT

async def get_user_id(token: str) -> str:
    """Xác thực JWT Supabase, cache Redis."""
    cache_key = f"auth:{hashlib.sha256(token.encode()).hexdigest()[:32]}"

    redis = await get_redis()
    if redis:
        cached = await redis.get(cache_key)
        if cached:
            return cached

    async with httpx.AsyncClient(timeout=SUPABASE_AUTH_TIMEOUT) as client:
        r = await client.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={"Authorization": f"Bearer {token}", "apikey": SUPABASE_ANON_KEY},
        )

    if r.status_code != 200:
        raise HTTPException(401, "Invalid or expired token")

    user_id: str = r.json().get("id", "")
    if not user_id:
        raise HTTPException(401, "Cannot extract user ID from token")

    if redis:
        await redis.setex(cache_key, SUPABASE_TOKEN_TTL, user_id)

    return user_id