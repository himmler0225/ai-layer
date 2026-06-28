"""Xác thực X-API-Key."""

from fastapi import Header, HTTPException

from app.config.settings import API_KEYS


async def verify_api_key(x_api_key: str = Header(...)):
    """Kiểm tra header X-API-Key."""
    if not API_KEYS or x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
