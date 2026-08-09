import asyncio
from typing import Any

import httpx

import app.config.settings as settings
from app.config.constants import DATA_MINER_MAX_CONN, DATA_MINER_MAX_KEEPALIVE, HTTP_MAX_ATTEMPTS, HTTP_RETRY_STATUSES
from app.config.logger import Logger, log_event
from app.exceptions import AiLayerUpstreamError
from app.utils.retry import retry_delay

logger = Logger.get(__name__)
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Get or lazily (re)create the shared `httpx.AsyncClient` for movie-aggregator-api.

    Recreates the client if it hasn't been created yet or was closed.

    Returns:
        The shared `httpx.AsyncClient` instance."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=settings.MOVIE_AGGREGATOR_URL,
            timeout=settings.MOVIE_AGGREGATOR_TIMEOUT,
            limits=httpx.Limits(
                max_connections=DATA_MINER_MAX_CONN,
                max_keepalive_connections=DATA_MINER_MAX_KEEPALIVE,
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
    """GET a movie-aggregator-api endpoint, retrying on network errors and
    retryable HTTP statuses with a backoff delay between attempts.

    The route is public (no API key), so no auth headers are sent.

    Args:
        path: Request path relative to the movie-aggregator-api base URL.
        params: Optional query parameters.

    Returns:
        The parsed JSON body, e.g. `{"source": ..., "data": ..., "pagination": ...}`.

    Raises:
        httpx.HTTPStatusError: If the response is a non-retryable error status.
        AiLayerUpstreamError: If all retry attempts are exhausted."""
    last_exc: Exception = AiLayerUpstreamError("Unknown error")
    for attempt in range(1, HTTP_MAX_ATTEMPTS + 1):
        try:
            r = await _get_client().get(path, params=params or {})
            if r.status_code in HTTP_RETRY_STATUSES:
                raise httpx.HTTPStatusError(f"{r.status_code} from movie-aggregator-api", request=r.request, response=r)
            r.raise_for_status()
            return r.json()
        except (httpx.NetworkError, httpx.TimeoutException) as e:
            last_exc = e
        except httpx.HTTPStatusError as e:
            if e.response.status_code not in HTTP_RETRY_STATUSES:
                raise
            last_exc = e
        if attempt < HTTP_MAX_ATTEMPTS:
            delay = retry_delay(attempt)
            logger.warning(
                log_event(
                    "movie_aggregator",
                    "request retry",
                    method="GET",
                    path=path,
                    attempt=attempt,
                    max_attempts=HTTP_MAX_ATTEMPTS,
                    delay_s=delay,
                )
            )
            await asyncio.sleep(delay)
        else:
            logger.error(
                log_event(
                    "movie_aggregator",
                    "request failed",
                    method="GET",
                    path=path,
                    attempts=HTTP_MAX_ATTEMPTS,
                )
            )
    raise AiLayerUpstreamError(str(last_exc), cause=last_exc) from last_exc
