import asyncio
from app.config.logger import Logger
from typing import Any, Dict

import httpx

from app.config.settings import DATA_MINER_URL, DATA_MINER_KEY

logger = Logger.get(__name__)

_HEADERS         = {"X-API-Key": DATA_MINER_KEY}
_MAX_ATTEMPTS    = 3
_RETRY_ON_STATUS = {502, 503, 504}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=DATA_MINER_URL, headers=_HEADERS, timeout=30)


async def _get(path: str, params: Dict = None) -> Any:
    last_exc: Exception = RuntimeError("Unknown error")
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            async with _client() as c:
                r = await c.get(path, params=params or {})
                if r.status_code in _RETRY_ON_STATUS:
                    raise httpx.HTTPStatusError(
                        f"{r.status_code} from data-miner",
                        request=r.request, response=r,
                    )
                r.raise_for_status()
                return r.json()
        except (httpx.NetworkError, httpx.TimeoutException) as e:
            last_exc = e
        except httpx.HTTPStatusError as e:
            if e.response.status_code not in _RETRY_ON_STATUS:
                raise
            last_exc = e

        if attempt < _MAX_ATTEMPTS:
            delay = 2 ** (attempt - 1)
            logger.warning("data-miner GET %s attempt %d/%d failed — retry in %ds", path, attempt, _MAX_ATTEMPTS, delay)
            await asyncio.sleep(delay)
        else:
            logger.error("data-miner GET %s — all %d attempts failed", path, _MAX_ATTEMPTS)

    raise last_exc


# ── Videos ────────────────────────────────────────────────────────────────────

async def search_youtube(query: str, max_results: int = 10, sort: str = "relevance") -> Dict:
    return await _get("/api/videos/search", {"q": query, "max_results": max_results, "sort": sort})


async def get_video_detail(video_id: str) -> Dict:
    return await _get(f"/api/videos/{video_id}")


async def get_video_comments(video_id: str, max_comments: int = 20, sort: str = "newest") -> Dict:
    return await _get(f"/api/videos/{video_id}/comments", {"limit": max_comments, "sort": sort})


async def get_trending(max_results: int = 20) -> Dict:
    return await _get("/api/videos/trending", {"limit": max_results})


async def get_shorts(max_results: int = 20) -> Dict:
    return await _get("/api/videos/shorts", {"limit": max_results})


async def get_live(query: str = "", max_results: int = 20) -> Dict:
    return await _get("/api/videos/live", {"q": query, "limit": max_results})


async def get_by_region(gl: str, hl: str, query: str, max_results: int = 20) -> Dict:
    return await _get("/api/videos/location", {"gl": gl, "hl": hl, "query": query, "max_results": max_results})


async def get_by_topic(topic: str, max_results: int = 20) -> Dict:
    return await _get("/api/videos/by-topic", {"topic": topic, "limit": max_results})


# ── Channels ──────────────────────────────────────────────────────────────────

async def get_channel_info(channel_id: str) -> Dict:
    return await _get(f"/api/channels/{channel_id}")


async def get_channel_videos(channel_id: str, max_results: int = 30) -> Dict:
    return await _get(f"/api/channels/{channel_id}/videos", {"limit": max_results})


async def get_channel_playlists(channel_id: str) -> Dict:
    return await _get(f"/api/channels/{channel_id}/playlists")


# ── Playlists ─────────────────────────────────────────────────────────────────

async def get_playlist_videos(playlist_id: str, max_results: int = 30) -> Dict:
    return await _get(f"/api/playlists/{playlist_id}/videos", {"limit": max_results})


# ── TikTok (via SociaVault) ───────────────────────────────────────────────────

async def tiktok_search(
    keyword: str,
    cursor: int = 0,
    sort_by: str = None,
    date_posted: str = None,
    region: str = None,
) -> Dict:
    params: Dict = {"q": keyword, "cursor": cursor}
    if sort_by:    params["sort_by"]     = sort_by
    if date_posted: params["date_posted"] = date_posted
    if region:     params["region"]      = region
    return await _get("/api/tiktok/search", params)


async def tiktok_video_info(url: str, get_transcript: bool = False, region: str = None) -> Dict:
    params: Dict = {"url": url}
    if get_transcript: params["get_transcript"] = "true"
    if region:         params["region"]         = region
    return await _get("/api/tiktok/video-info", params)


async def tiktok_comments(url: str, cursor: int = 0) -> Dict:
    return await _get("/api/tiktok/comments", {"url": url, "cursor": cursor})


async def tiktok_profile(handle: str) -> Dict:
    return await _get(f"/api/tiktok/profiles/{handle}")
