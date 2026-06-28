"""HTTP client gọi data-miner API (YouTube/TikTok crawl)."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import httpx

import app.config.settings as settings
from app.config.constants import (DATA_MINER_MAX_CONN,
                                  DATA_MINER_MAX_KEEPALIVE, HTTP_MAX_ATTEMPTS,
                                  HTTP_RETRY_STATUSES)
from app.config.headers import get_data_miner_headers
from app.config.logger import Logger

logger = Logger.get(__name__)

_MAX_ATTEMPTS = HTTP_MAX_ATTEMPTS
_RETRY_ON_STATUS = HTTP_RETRY_STATUSES

_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    """Lấy hoặc tạo httpx client dùng chung."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=settings.DATA_MINER_URL,
            headers=get_data_miner_headers(settings.DATA_MINER_KEY),
            timeout=settings.DATA_MINER_TIMEOUT,
            limits=httpx.Limits(
                max_connections=DATA_MINER_MAX_CONN,
                max_keepalive_connections=DATA_MINER_MAX_KEEPALIVE,
            ),
        )
    return _client


async def close_client() -> None:
    """Đóng httpx client khi shutdown."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


async def _get(path: str, params: Dict = None) -> Any:
    """Gọi GET sang data-miner, tự retry khi lỗi mạng hoặc 5xx."""
    last_exc: Exception = RuntimeError("Unknown error")
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            r = await _get_client().get(
                path,
                params=params or {},
                headers=get_data_miner_headers(settings.DATA_MINER_KEY),
            )
            if r.status_code in _RETRY_ON_STATUS:
                raise httpx.HTTPStatusError(
                    f"{r.status_code} from data-miner", request=r.request, response=r
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
            logger.warning(
                "[data_miner] GET %s retry=%d/%d delay=%ds",
                path,
                attempt,
                _MAX_ATTEMPTS,
                delay,
            )
            await asyncio.sleep(delay)
        else:
            logger.error("[data_miner] GET %s failed attempts=%d", path, _MAX_ATTEMPTS)
    raise last_exc


async def search_youtube(
    query: str, max_results: int = 10, sort: str = "relevance"
) -> Dict:
    """Tìm video YouTube theo từ khóa."""
    return await _get(
        "/api/videos/search", {"q": query, "max_results": max_results, "sort": sort}
    )


async def get_video_detail(video_id: str) -> Dict:
    """Lấy metadata chi tiết một video."""
    return await _get(f"/api/videos/{video_id}")


async def get_video_comments(
    video_id: str, max_comments: int = 20, sort: str = "newest"
) -> Dict:
    """Lấy comment của một video."""
    return await _get(
        f"/api/videos/{video_id}/comments", {"limit": max_comments, "sort": sort}
    )


async def get_video_comments_batch(
    video_ids: list, max_per_video: int = 20, sort: str = "top"
) -> Dict:
    """Lấy comment nhiều video song song."""
    return await _get(
        "/api/videos/comments/batch",
        {
            "video_ids": ",".join(video_ids),
            "limit": max_per_video,
            "sort": sort,
        },
    )


async def get_video_transcript(video_id: str) -> Dict:
    """Lấy transcript/phụ đề một video."""
    return await _get(f"/api/videos/{video_id}/transcript")


async def get_video_transcript_batch(video_ids: list) -> Dict:
    """Lấy transcript nhiều video song song."""
    return await _get(
        "/api/videos/transcript/batch", {"video_ids": ",".join(video_ids)}
    )


async def get_trending(max_results: int = 20) -> Dict:
    """Lấy video đang trending."""
    return await _get("/api/videos/trending", {"limit": max_results})


async def get_shorts(max_results: int = 20) -> Dict:
    """Lấy danh sách YouTube Shorts."""
    return await _get("/api/videos/shorts", {"limit": max_results})


async def get_live(query: str = "", max_results: int = 20) -> Dict:
    """Lấy video đang phát trực tiếp."""
    return await _get("/api/videos/live", {"q": query, "limit": max_results})


async def get_by_region(gl: str, hl: str, query: str, max_results: int = 20) -> Dict:
    """Tìm video theo mã quốc gia/khu vực."""
    return await _get(
        "/api/videos/location",
        {"gl": gl, "hl": hl, "query": query, "max_results": max_results},
    )


async def get_by_topic(topic: str, max_results: int = 20) -> Dict:
    """Lấy video theo chủ đề."""
    return await _get("/api/videos/by-topic", {"topic": topic, "limit": max_results})


async def get_channel_info(channel_id: str) -> Dict:
    """Lấy thông tin kênh YouTube."""
    return await _get(f"/api/channels/{channel_id}")


async def get_channel_videos(channel_id: str, max_results: int = 30) -> Dict:
    """Lấy video của một kênh."""
    return await _get(f"/api/channels/{channel_id}/videos", {"limit": max_results})


async def get_channel_playlists(channel_id: str) -> Dict:
    """Lấy playlist của kênh."""
    return await _get(f"/api/channels/{channel_id}/playlists")


async def get_playlist_videos(playlist_id: str, max_results: int = 30) -> Dict:
    """Lấy video trong một playlist."""
    return await _get(f"/api/playlists/{playlist_id}/videos", {"limit": max_results})


async def tiktok_search(
    keyword: str,
    cursor: int = 0,
    sort_by: str = None,
    date_posted: str = None,
    region: str = None,
) -> Dict:
    """Tìm kiếm video TikTok."""
    params: Dict = {"q": keyword, "cursor": cursor}
    if sort_by:
        params["sort_by"] = sort_by
    if date_posted:
        params["date_posted"] = date_posted
    if region:
        params["region"] = region
    return await _get("/api/tiktok/search", params)


async def tiktok_video_info(url: str) -> Dict:
    """Lấy metadata video TikTok từ URL."""
    return await _get("/api/tiktok/video-info", {"url": url})


async def tiktok_comments(aweme_id: str, cursor: int = 0, count: int = 20) -> Dict:
    """Lấy comment video TikTok."""
    return await _get(
        "/api/tiktok/comments", {"aweme_id": aweme_id, "cursor": cursor, "count": count}
    )


async def tiktok_profile(handle: str) -> Dict:
    """Lấy thông tin profile TikTok."""
    return await _get(f"/api/tiktok/profiles/{handle}")


async def tiktok_transcript(aweme_id: str) -> Dict:
    """Lấy transcript/lời thoại video TikTok."""
    return await _get("/api/tiktok/transcript", {"aweme_id": aweme_id})
