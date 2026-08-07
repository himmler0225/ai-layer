from fastapi import Header
from app.exceptions import AiLayerAuthError
from app.config.settings import API_KEYS


async def verify_api_key(x_api_key: str = Header(...)):
    """FastAPI dependency that validates the `X-API-Key` request header.

    Args:
        x_api_key: The `X-API-Key` header value (required).

    Raises:
        AiLayerAuthError: If no API keys are configured or the given key
            isn't in the configured `API_KEYS` set."""
    if not API_KEYS or x_api_key not in API_KEYS:
        raise AiLayerAuthError("API key không hợp lệ", message_key="errors.invalid_api_key")
