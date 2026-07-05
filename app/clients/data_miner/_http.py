import asyncio
from typing import Any

import httpx

from app.clients import config as dm_config
from app.config.headers import get_data_miner_headers
from app.config.logger import Logger
from app.exceptions import AiLayerUpstreamError
from app.utils.retry import retry_delay

logger = Logger.get(__name__)
_client: httpx.AsyncClient | None = None


def _headers() -> dict[str, str]:
    from app.i18n import get_locale

    headers = get_data_miner_headers(dm_config.api_key(), dm_config.service_token())
    headers["X-Locale"] = get_locale()
    return headers


def _get_client() -> httpx.AsyncClient:
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
    global _client
    if _client and (not _client.is_closed):
        await _client.aclose()
        _client = None


async def get(path: str, params: dict | None = None) -> Any:
    last_exc: Exception = AiLayerUpstreamError("Unknown error")
    for attempt in range(1, dm_config.HTTP_MAX_ATTEMPTS + 1):
        try:
            r = await _get_client().get(path, params=params or {}, headers=_headers())
            if r.status_code in dm_config.HTTP_RETRY_STATUSES:
                raise httpx.HTTPStatusError(f"{r.status_code} from data-miner", request=r.request, response=r)
            r.raise_for_status()
            return r.json()
        except (httpx.NetworkError, httpx.TimeoutException) as e:
            last_exc = e
        except httpx.HTTPStatusError as e:
            if e.response.status_code not in dm_config.HTTP_RETRY_STATUSES:
                raise
            last_exc = e
        if attempt < dm_config.HTTP_MAX_ATTEMPTS:
            delay = retry_delay(attempt)
            logger.warning(
                "[data_miner] GET %s retry=%d/%d delay=%ds",
                path,
                attempt,
                dm_config.HTTP_MAX_ATTEMPTS,
                delay,
            )
            await asyncio.sleep(delay)
        else:
            logger.error("[data_miner] GET %s failed attempts=%d", path, dm_config.HTTP_MAX_ATTEMPTS)
    raise AiLayerUpstreamError(str(last_exc), cause=last_exc) from last_exc
