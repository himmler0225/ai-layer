"""Thực thi tool agent — mỗi hàm _youtube_*/_tiktok_* ủy quyền sang data-miner."""

from __future__ import annotations

from typing import Any, Dict

import jsonschema
from app.clients import data_miner
import app.config.settings as _cfg
from app.services.url_extractor import extract_id_from_url as _url_extract
from app.tools.definitions import YOUTUBE_TOOLS, TIKTOK_TOOLS, UTIL_TOOLS
from app.tools.rag_definitions import RAG_TOOLS
from app.rag import search as rag_search

_RAG_TOOL_NAMES = frozenset(t["name"] for t in RAG_TOOLS)

_SCHEMAS: Dict[str, Dict] = {
    tool["name"]: tool["parameters"]
    for tool in (*(RAG_TOOLS if _cfg.RAG_ENABLED else []), *YOUTUBE_TOOLS, *TIKTOK_TOOLS, *UTIL_TOOLS)
}

async def _youtube_search(inp: Dict) -> Any:
    """Tìm video YouTube theo từ khóa."""
    return await data_miner.search_youtube(
        query=inp["keyword"], max_results=inp.get("max_results", 5), sort=inp.get("sort", "relevance"),
    )

async def _youtube_get_by_topic(inp: Dict) -> Any:
    """Lấy video YouTube theo chủ đề."""
    return await data_miner.get_by_topic(topic=inp["topic"], max_results=inp.get("max_results", 20))

async def _youtube_get_shorts(inp: Dict) -> Any:
    """Lấy danh sách YouTube Shorts."""
    return await data_miner.get_shorts(max_results=inp.get("max_results", 20))

async def _youtube_get_live(inp: Dict) -> Any:
    """Lấy video đang phát trực tiếp trên YouTube."""
    return await data_miner.get_live(query=inp.get("query", ""), max_results=inp.get("max_results", 20))

async def _youtube_get_by_region(inp: Dict) -> Any:
    """Tìm video YouTube theo quốc gia/khu vực."""
    return await data_miner.get_by_region(
        gl=inp["gl"], hl=inp.get("hl", "vi"), query=inp["query"], max_results=inp.get("max_results", 20),
    )

async def _youtube_get_detail(inp: Dict) -> Any:
    """Lấy metadata chi tiết một video YouTube."""
    return await data_miner.get_video_detail(inp["video_id"])

async def _youtube_get_comments(inp: Dict) -> Any:
    """Lấy comment của một video YouTube."""
    return await data_miner.get_video_comments(
        video_id=inp["video_id"],
        max_comments=inp.get("max_comments", _cfg.AGENT_MAX_COMMENTS),
        sort=inp.get("sort", "top"),
    )

async def _youtube_get_comments_batch(inp: Dict) -> Any:
    """Lấy comment nhiều video YouTube song song."""
    raw = inp.get("video_ids", [])
    if isinstance(raw, str):
        ids = [v.strip() for v in raw.split(",") if v.strip()]
    else:
        ids = [str(v).strip() for v in raw if str(v).strip()]
    sort = inp.get("sort", "top")
    if sort not in ("top", "newest"):
        sort = "top"
    return await data_miner.get_video_comments_batch(
        video_ids=ids[:8],
        max_per_video=inp.get("max_per_video", _cfg.AGENT_MAX_COMMENTS),
        sort=sort,
    )

async def _youtube_get_transcript(inp: Dict) -> Any:
    """Lấy phụ đề/transcript một video YouTube."""
    return await data_miner.get_video_transcript(inp["video_id"])

async def _youtube_get_transcript_batch(inp: Dict) -> Any:
    """Lấy transcript nhiều video YouTube song song."""
    raw = inp.get("video_ids", [])
    if isinstance(raw, str):
        ids = [v.strip() for v in raw.split(",") if v.strip()]
    else:
        ids = [str(v).strip() for v in raw if str(v).strip()]
    return await data_miner.get_video_transcript_batch(ids[:8])

async def _youtube_get_channel_info(inp: Dict) -> Any:
    """Lấy thông tin kênh YouTube."""
    return await data_miner.get_channel_info(inp["channel_id"])

async def _youtube_get_channel_videos(inp: Dict) -> Any:
    """Lấy danh sách video của kênh YouTube."""
    return await data_miner.get_channel_videos(channel_id=inp["channel_id"], max_results=inp.get("max_results", 30))

async def _youtube_get_channel_playlists(inp: Dict) -> Any:
    """Lấy playlist của kênh YouTube."""
    return await data_miner.get_channel_playlists(inp["channel_id"])

async def _youtube_get_playlist_videos(inp: Dict) -> Any:
    """Lấy video trong một playlist YouTube."""
    return await data_miner.get_playlist_videos(playlist_id=inp["playlist_id"], max_results=inp.get("max_results", 30))

async def _tiktok_search(inp: Dict) -> Any:
    """Tìm video TikTok theo từ khóa."""
    return await data_miner.tiktok_search(
        keyword=inp["keyword"], cursor=inp.get("cursor", 0),
        sort_by=inp.get("sort_by"), date_posted=inp.get("date_posted"), region=inp.get("region"),
    )

async def _tiktok_video_info(inp: Dict) -> Any:
    """Lấy metadata video TikTok từ URL."""
    return await data_miner.tiktok_video_info(url=inp["url"])

async def _tiktok_comments(inp: Dict) -> Any:
    """Lấy comment video TikTok."""
    return await data_miner.tiktok_comments(
        aweme_id=inp["aweme_id"], cursor=inp.get("cursor", 0), count=inp.get("count", 20),
    )

async def _tiktok_profile(inp: Dict) -> Any:
    """Lấy thông tin profile TikTok."""
    return await data_miner.tiktok_profile(inp["handle"])

async def _tiktok_transcript(inp: Dict) -> Any:
    """Lấy transcript/lời thoại video TikTok."""
    return await data_miner.tiktok_transcript(aweme_id=inp["aweme_id"])

async def _extract_id_from_url(inp: Dict) -> Any:
    """Trích video_id YouTube hoặc URL TikTok từ link."""
    return _url_extract(url=inp["url"])

_REGISTRY = {
    "youtube_search":                _youtube_search,
    "youtube_get_by_topic":          _youtube_get_by_topic,
    "youtube_get_shorts":            _youtube_get_shorts,
    "youtube_get_live":              _youtube_get_live,
    "youtube_get_by_region":         _youtube_get_by_region,
    "youtube_get_detail":            _youtube_get_detail,
    "youtube_get_comments":          _youtube_get_comments,
    "youtube_get_comments_batch":    _youtube_get_comments_batch,
    "youtube_get_transcript":        _youtube_get_transcript,
    "youtube_get_transcript_batch":  _youtube_get_transcript_batch,
    "youtube_get_channel_info":      _youtube_get_channel_info,
    "youtube_get_channel_videos":    _youtube_get_channel_videos,
    "youtube_get_channel_playlists": _youtube_get_channel_playlists,
    "youtube_get_playlist_videos":   _youtube_get_playlist_videos,
    "tiktok_search":                 _tiktok_search,
    "tiktok_video_info":             _tiktok_video_info,
    "tiktok_comments":               _tiktok_comments,
    "tiktok_profile":                _tiktok_profile,
    "tiktok_transcript":             _tiktok_transcript,
    "extract_id_from_url":           _extract_id_from_url,
}

async def execute_tool(name: str, inputs: Dict, **kwargs) -> Dict:
    """Chạy tool theo tên: kiểm tra input rồi gọi handler tương ứng."""
    schema = _SCHEMAS.get(name)
    if schema:
        try:
            jsonschema.validate(instance=inputs, schema=schema)
        except jsonschema.ValidationError as e:
            return {"error": f"Invalid input for {name}: {e.message}"}

    if name in _RAG_TOOL_NAMES:
        if not _cfg.RAG_ENABLED:
            return {"error": "RAG disabled"}
        if name == "search_product_summary":
            return await rag_search.search_aspect_summary(
                inputs["product_id"], inputs["query"], aspect=inputs.get("aspect")
            )
        if name == "search_aspect_evidence":
            return await rag_search.search_aspect_evidence(
                inputs["product_id"], inputs["query"], aspect=inputs.get("aspect")
            )
        if name == "get_raw_reviews":
            return await rag_search.get_raw_reviews(
                inputs["product_id"], limit=int(inputs.get("limit") or 10)
            )

    fn = _REGISTRY.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}

    try:
        result = await fn(inputs)
        return result if isinstance(result, dict) else {"data": result}
    except Exception as e:
        return {"error": str(e), "tool": name}