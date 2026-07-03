from fastapi import Header
from app.exceptions import AiLayerAuthError
from app.config.settings import API_KEYS


async def verify_api_key(x_api_key: str = Header(...)):
    """Xác minh api key (async).

    Args:
        x_api_key: (str, mặc định Header(...)) Tham số `x_api_key`."""
    if not API_KEYS or x_api_key not in API_KEYS:
        raise AiLayerAuthError("Invalid API key")
