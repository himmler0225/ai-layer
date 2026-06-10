from __future__ import annotations

from typing import Optional

import httpx

from app.config.logger import Logger

logger = Logger.get(__name__)

_PROVIDERS = ("tinyurl", "isgd")

_http: Optional[httpx.AsyncClient] = None

def _get_http() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(timeout=10)
    return _http

async def _call_provider(url: str, api_url: str, params: dict, provider: str) -> dict:
    try:
        r = await _get_http().get(api_url, params=params)
        r.raise_for_status()
        short = r.text.strip()
        logger.info("%s: %s → %s", provider, url[:60], short)
        return {"original": url, "short": short, "provider": provider}
    except Exception as e:
        logger.warning("%s failed: %s", provider, e)
        return {"error": str(e)}

async def shorten_url(url: str, provider: str = "tinyurl") -> dict:
    if provider == "tinyurl":
        return await _call_provider(url, "https://tinyurl.com/api-create.php", {"url": url}, "tinyurl")
    if provider == "isgd":
        return await _call_provider(url, "https://is.gd/create.php", {"format": "simple", "url": url}, "is.gd")
    return {"error": f"Unknown provider: {provider}. Available: {list(_PROVIDERS)}"}
