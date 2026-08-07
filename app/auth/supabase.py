import hashlib
import httpx
from app.exceptions import AiLayerAuthError
from app.cache.client import get_redis
from app.config.constants import SUPABASE_AUTH_TIMEOUT
from app.config.headers import get_supabase_auth_headers
from app.config.settings import SUPABASE_ANON_KEY, SUPABASE_TOKEN_TTL, SUPABASE_URL


async def get_user_id(token: str) -> str:
    """Resolve a Supabase JWT to a user id, using a Redis cache when available.

    Looks up a cached id keyed by a SHA-256 hash of the token; on a miss,
    validates the token against Supabase's `/auth/v1/user` endpoint and
    caches the result for `SUPABASE_TOKEN_TTL` seconds.

    Args:
        token: The bearer token to validate.

    Returns:
        The authenticated user's id.

    Raises:
        AiLayerAuthError: If the token is invalid/expired or the user id
            can't be extracted from the response."""
    cache_key = f"auth:{hashlib.sha256(token.encode()).hexdigest()[:32]}"
    redis = await get_redis()
    if redis:
        cached = await redis.get(cache_key)
        if cached:
            return cached
    async with httpx.AsyncClient(timeout=SUPABASE_AUTH_TIMEOUT) as client:
        r = await client.get(
            f"{SUPABASE_URL}/auth/v1/user", headers=get_supabase_auth_headers(token, SUPABASE_ANON_KEY)
        )
    if r.status_code != 200:
        raise AiLayerAuthError("Token không hợp lệ hoặc đã hết hạn", message_key="errors.invalid_token")
    user_id: str = r.json().get("id", "")
    if not user_id:
        raise AiLayerAuthError("Không lấy được thông tin user từ token", message_key="errors.cannot_extract_user")
    if redis:
        await redis.setex(cache_key, SUPABASE_TOKEN_TTL, user_id)
    return user_id
