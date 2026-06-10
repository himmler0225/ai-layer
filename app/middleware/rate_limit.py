from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

def _key_by_api_key(request: Request) -> str:
    return request.headers.get("X-API-Key") or request.client.host or "unknown"

limiter = Limiter(key_func=_key_by_api_key)
rate_limit_exceeded_handler = _rate_limit_exceeded_handler

__all__ = ["limiter", "rate_limit_exceeded_handler", "RateLimitExceeded"]
