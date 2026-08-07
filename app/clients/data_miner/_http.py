import asyncio
from typing import Any

import httpx

from app.clients import config as dm_config
from app.config.headers import get_data_miner_headers
from app.config.logger import Logger, log_event
from app.exceptions import AiLayerUpstreamError
from app.utils.retry import retry_delay

logger = Logger.get(__name__)
_client: httpx.AsyncClient | None = None


def _headers() -> dict[str, str]:
    """Build the auth + locale headers to send with each data-miner request.

    Returns:
        Headers including data-miner auth headers plus `X-Lang`/`X-Locale`
        set to the current request locale."""
    from app.i18n import get_locale

    headers = get_data_miner_headers(dm_config.api_key(), dm_config.service_token())
    locale = get_locale()
    headers["X-Lang"] = locale
    headers["X-Locale"] = locale  # legacy alias
    return headers


def _get_client() -> httpx.AsyncClient:
    """Get or lazily (re)create the shared `httpx.AsyncClient` for data-miner.

    Recreates the client if it hasn't been created yet or was closed.

    Returns:
        The shared `httpx.AsyncClient` instance."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=dm_config.base_url(),
            headers=_headers(),
            timeout=dm_config.timeout(),
            limits=httpx.Limits(
                max_connections=dm_config.DATA_MINER_MAX_CONN,
                max_keepalive_connections=dm_config.DATA_MINER_MAX_KEEPALIVE,
            ),
        )
    return _client


async def close_client() -> None:
    """Close the shared HTTP client, if open, and clear it.

    Returns:
        None."""
    global _client
    if _client and (not _client.is_closed):
        await _client.aclose()
        _client = None


async def get(path: str, params: dict | None = None) -> Any:
    """GET a data-miner endpoint, retrying on network errors and retryable
    HTTP statuses with a backoff delay between attempts.

    Args:
        path: Request path relative to the data-miner base URL.
        params: Optional query parameters.

    Returns:
        The parsed JSON body — unwrapped to `body["data"]` if the response
        looks like `{"success": ..., "data": ...}`, otherwise the raw body.

    Raises:
        httpx.HTTPStatusError: If the response is a non-retryable error status.
        AiLayerUpstreamError: If all retry attempts are exhausted."""
    last_exc: Exception = AiLayerUpstreamError("Unknown error")
    for attempt in range(1, dm_config.HTTP_MAX_ATTEMPTS + 1):
        try:
            r = await _get_client().get(path, params=params or {}, headers=_headers())
            if r.status_code in dm_config.HTTP_RETRY_STATUSES:
                raise httpx.HTTPStatusError(f"{r.status_code} from data-miner", request=r.request, response=r)
            r.raise_for_status()
            body = r.json()
            if isinstance(body, dict) and "success" in body and "data" in body:
                return body["data"]
            return body
        except (httpx.NetworkError, httpx.TimeoutException) as e:
            last_exc = e
        except httpx.HTTPStatusError as e:
            if e.response.status_code not in dm_config.HTTP_RETRY_STATUSES:
                raise
            last_exc = e
        if attempt < dm_config.HTTP_MAX_ATTEMPTS:
            delay = retry_delay(attempt)
            logger.warning(
                log_event(
                    "data_miner",
                    "request retry",
                    method="GET",
                    path=path,
                    attempt=attempt,
                    max_attempts=dm_config.HTTP_MAX_ATTEMPTS,
                    delay_s=delay,
                )
            )
            await asyncio.sleep(delay)
        else:
            logger.error(
                log_event(
                    "data_miner",
                    "request failed",
                    method="GET",
                    path=path,
                    attempts=dm_config.HTTP_MAX_ATTEMPTS,
                )
            )
    raise AiLayerUpstreamError(str(last_exc), cause=last_exc) from last_exc
