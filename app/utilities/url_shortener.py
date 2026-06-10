from app.config.logger import Logger
from urllib.parse import quote

import httpx

logger = Logger.get(__name__)

_PROVIDERS = [
    "tinyurl",
    "isgd",
]


async def shorten_url(url: str, provider: str = "tinyurl") -> dict:
    if provider == "tinyurl":
        return await _tinyurl(url)
    if provider == "isgd":
        return await _isgd(url)
    return {"error": f"Unknown provider: {provider}. Available: {_PROVIDERS}"}


async def _tinyurl(url: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                "https://tinyurl.com/api-create.php",
                params={"url": url},
            )
            r.raise_for_status()
            short = r.text.strip()
            logger.info("TinyURL: %s → %s", url[:60], short)
            return {"original": url, "short": short, "provider": "tinyurl"}
    except Exception as e:
        logger.warning("TinyURL failed: %s", e)
        return {"error": str(e)}


async def _isgd(url: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                "https://is.gd/create.php",
                params={"format": "simple", "url": url},
            )
            r.raise_for_status()
            short = r.text.strip()
            logger.info("is.gd: %s → %s", url[:60], short)
            return {"original": url, "short": short, "provider": "is.gd"}
    except Exception as e:
        logger.warning("is.gd failed: %s", e)
        return {"error": str(e)}
