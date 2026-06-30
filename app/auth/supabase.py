from __future__ import annotations
import hashlib
import httpx
from app.exceptions import AiLayerAuthError
from app.cache.client import get_redis
from app.config.constants import SUPABASE_AUTH_TIMEOUT
from app.config.headers import get_supabase_auth_headers
from app.config.settings import SUPABASE_ANON_KEY, SUPABASE_TOKEN_TTL, SUPABASE_URL

async def get_user_id(token: str) -> str:
    """Lấy user id (async).

    Args:
        token: (str) Tham số `token`.

    Returns:
        (str) Kết quả trả về."""
    cache_key = f'auth:{hashlib.sha256(token.encode()).hexdigest()[:32]}'
    redis = await get_redis()
    if redis:
        cached = await redis.get(cache_key)
        if cached:
            return cached
    async with httpx.AsyncClient(timeout=SUPABASE_AUTH_TIMEOUT) as client:
        r = await client.get(f'{SUPABASE_URL}/auth/v1/user', headers=get_supabase_auth_headers(token, SUPABASE_ANON_KEY))
    if r.status_code != 200:
        raise AiLayerAuthError('Invalid or expired token')
    user_id: str = r.json().get('id', '')
    if not user_id:
        raise AiLayerAuthError('Cannot extract user ID from token')
    if redis:
        await redis.setex(cache_key, SUPABASE_TOKEN_TTL, user_id)
    return user_id
