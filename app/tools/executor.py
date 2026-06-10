from typing import Any, Dict

from app.clients import data_miner
from app.services.url_extractor import extract_id_from_url as _url_extract


# ── Videos ────────────────────────────────────────────────────────────────────

async def _youtube_search(inp: Dict) -> Any:
    return await data_miner.search_youtube(
        query=inp["keyword"],
        max_results=inp.get("max_results", 5),
        sort=inp.get("sort", "relevance"),
    )

async def _youtube_get_by_topic(inp: Dict) -> Any:
    return await data_miner.get_by_topic(
        topic=inp["topic"],
        max_results=inp.get("max_results", 20),
    )

async def _youtube_get_shorts(inp: Dict) -> Any:
    return await data_miner.get_shorts(max_results=inp.get("max_results", 20))

async def _youtube_get_live(inp: Dict) -> Any:
    return await data_miner.get_live(
        query=inp.get("query", ""),
        max_results=inp.get("max_results", 20),
    )

async def _youtube_get_by_region(inp: Dict) -> Any:
    return await data_miner.get_by_region(
        gl=inp["gl"],
        hl=inp.get("hl", "vi"),
        query=inp["query"],
        max_results=inp.get("max_results", 20),
    )

async def _youtube_get_detail(inp: Dict) -> Any:
    return await data_miner.get_video_detail(inp["video_id"])

async def _youtube_get_comments(inp: Dict) -> Any:
    return await data_miner.get_video_comments(
        video_id=inp["video_id"],
        max_comments=min(inp.get("max_comments", 20), 20),
        sort=inp.get("sort", "newest"),
    )


# ── Channels ──────────────────────────────────────────────────────────────────

async def _youtube_get_channel_info(inp: Dict) -> Any:
    return await data_miner.get_channel_info(inp["channel_id"])

async def _youtube_get_channel_videos(inp: Dict) -> Any:
    return await data_miner.get_channel_videos(
        channel_id=inp["channel_id"],
        max_results=inp.get("max_results", 30),
    )

async def _youtube_get_channel_playlists(inp: Dict) -> Any:
    return await data_miner.get_channel_playlists(inp["channel_id"])


# ── Playlists ─────────────────────────────────────────────────────────────────

async def _youtube_get_playlist_videos(inp: Dict) -> Any:
    return await data_miner.get_playlist_videos(
        playlist_id=inp["playlist_id"],
        max_results=inp.get("max_results", 30),
    )


# ── TikTok (via SociaVault) ───────────────────────────────────────────────────

async def _tiktok_search(inp: Dict) -> Any:
    return await data_miner.tiktok_search(
        keyword=inp["keyword"],
        cursor=inp.get("cursor", 0),
        sort_by=inp.get("sort_by"),
        date_posted=inp.get("date_posted"),
        region=inp.get("region"),
    )

async def _tiktok_video_info(inp: Dict) -> Any:
    return await data_miner.tiktok_video_info(
        url=inp["url"],
        get_transcript=inp.get("get_transcript", False),
        region=inp.get("region"),
    )

async def _tiktok_comments(inp: Dict) -> Any:
    return await data_miner.tiktok_comments(
        url=inp["url"],
        cursor=inp.get("cursor", 0),
    )

async def _tiktok_profile(inp: Dict) -> Any:
    return await data_miner.tiktok_profile(inp["handle"])


# ── Utils ─────────────────────────────────────────────────────────────────────

async def _extract_id_from_url(inp: Dict) -> Any:
    return _url_extract(url=inp["url"])


# ── Registry ──────────────────────────────────────────────────────────────────

_REGISTRY = {
    "youtube_search":              _youtube_search,
    "youtube_get_by_topic":        _youtube_get_by_topic,
    "youtube_get_shorts":          _youtube_get_shorts,
    "youtube_get_live":            _youtube_get_live,
    "youtube_get_by_region":       _youtube_get_by_region,
    "youtube_get_detail":          _youtube_get_detail,
    "youtube_get_comments":        _youtube_get_comments,
    "youtube_get_channel_info":    _youtube_get_channel_info,
    "youtube_get_channel_videos":  _youtube_get_channel_videos,
    "youtube_get_channel_playlists": _youtube_get_channel_playlists,
    "youtube_get_playlist_videos": _youtube_get_playlist_videos,
    "tiktok_search":               _tiktok_search,
    "tiktok_video_info":           _tiktok_video_info,
    "tiktok_comments":             _tiktok_comments,
    "tiktok_profile":              _tiktok_profile,
    "extract_id_from_url":         _extract_id_from_url,
}


async def execute_tool(name: str, inputs: Dict) -> Dict:
    fn = _REGISTRY.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        result = await fn(inputs)
        return result if isinstance(result, dict) else {"data": result}
    except Exception as e:
        return {"error": str(e), "tool": name}
