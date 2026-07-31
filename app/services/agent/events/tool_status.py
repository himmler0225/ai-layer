import json
from typing import Any

from app.i18n import both


def _clip(text: str, n: int = 48) -> str:
    """(Nội bộ) Clip `_clip`.

    Args:
        text: (str) Tham số `text`.
        n: (int, mặc định 48) Tham số `n`.

    Returns:
        (str) Kết quả trả về."""
    s = (text or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _ids(raw: Any) -> list[str]:
    """(Nội bộ) Ids `_ids`.

    Args:
        raw: (Any) Tham số `raw`.

    Returns:
        (list[str]) Kết quả trả về."""
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str):
        return [x.strip() for x in raw.split(",") if x.strip()]
    return []


def _parse_args(arguments: str | None) -> dict:
    """(Nội bộ) Phân tích args.

    Args:
        arguments: (str | None) Tham số `arguments`.

    Returns:
        (dict) Kết quả trả về."""
    if not arguments:
        return {}
    try:
        parsed = json.loads(arguments)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def tool_status(tool: str, args: dict) -> tuple[str, str]:
    """Tool status.

    Args:
        tool: (str) Tham số `tool`.
        args: (dict) Tham số `args`.

    Returns:
        (tuple[str, str]) Kết quả trả về."""
    a = args or {}
    if tool == "youtube_search":
        q = _clip(a.get("keyword") or a.get("query") or "")
        return both("agent.tool.youtube_search", q=q) if q else both("agent.tool.youtube_search.generic")
    if tool == "youtube_get_comments":
        vid = a.get("video_id") or ""
        return both("agent.tool.youtube_get_comments", vid=vid) if vid else both("agent.tool.youtube_get_comments.generic")
    if tool == "youtube_get_comments_batch":
        ids = _ids(a.get("video_ids"))
        n = len(ids)
        if n == 1:
            return both("agent.tool.youtube_get_comments_batch.one", id=ids[0])
        if n > 1:
            return both("agent.tool.youtube_get_comments_batch.many", n=n, id=ids[0])
        return both("agent.tool.youtube_get_comments_batch.generic")
    if tool in ("youtube_get_transcript",):
        vid = a.get("video_id") or ""
        return (
            both("agent.tool.youtube_get_transcript", vid=vid)
            if vid
            else both("agent.tool.youtube_get_transcript.generic")
        )
    if tool == "youtube_get_transcript_batch":
        ids = _ids(a.get("video_ids"))
        n = len(ids)
        if n == 1:
            return both("agent.tool.youtube_get_transcript_batch.one", id=ids[0])
        if n > 1:
            return both("agent.tool.youtube_get_transcript_batch.many", n=n, id=ids[0])
        return both("agent.tool.youtube_get_transcript_batch.generic")
    if tool == "youtube_get_detail":
        vid = a.get("video_id") or ""
        return both("agent.tool.youtube_get_detail", vid=vid) if vid else both("agent.tool.youtube_get_detail.generic")
    if tool == "youtube_get_by_topic":
        topic = a.get("topic") or ""
        return (
            both("agent.tool.youtube_get_by_topic", topic=topic)
            if topic
            else both("agent.tool.youtube_get_by_topic.generic")
        )
    if tool == "youtube_get_by_region":
        q = _clip(a.get("query") or "")
        gl = a.get("gl") or ""
        return (
            both("agent.tool.youtube_get_by_region", gl=gl, q=q)
            if q
            else both("agent.tool.youtube_get_by_region.generic", gl=gl)
        )
    if tool == "youtube_get_channel_info":
        ch = _clip(a.get("channel_id") or "")
        return (
            both("agent.tool.youtube_get_channel_info", ch=ch)
            if ch
            else both("agent.tool.youtube_get_channel_info.generic")
        )
    if tool == "youtube_get_channel_videos":
        ch = _clip(a.get("channel_id") or "")
        return (
            both("agent.tool.youtube_get_channel_videos", ch=ch)
            if ch
            else both("agent.tool.youtube_get_channel_videos.generic")
        )
    if tool == "tiktok_search":
        q = _clip(a.get("keyword") or "")
        return both("agent.tool.tiktok_search", q=q) if q else both("agent.tool.tiktok_search.generic")
    if tool == "tiktok_comments":
        aweme = a.get("aweme_id") or ""
        return both("agent.tool.tiktok_comments", aweme=aweme) if aweme else both("agent.tool.tiktok_comments.generic")
    if tool == "tiktok_transcript":
        aweme = a.get("aweme_id") or ""
        return (
            both("agent.tool.tiktok_transcript", aweme=aweme)
            if aweme
            else both("agent.tool.tiktok_transcript.generic")
        )
    if tool == "tiktok_video_info":
        url = _clip(a.get("url") or "")
        return both("agent.tool.tiktok_video_info.with_url") if url else both("agent.tool.tiktok_video_info.no_url")
    if tool == "tiktok_profile":
        handle = a.get("handle") or ""
        return both("agent.tool.tiktok_profile", handle=handle) if handle else both("agent.tool.tiktok_profile.generic")
    if tool == "search_movie_summary":
        pid = _clip(a.get("movie_id") or "")
        return (
            both("agent.tool.search_movie_summary", pid=pid)
            if pid
            else both("agent.tool.search_movie_summary.generic")
        )
    if tool == "search_aspect_evidence":
        aspect = a.get("aspect") or ""
        pid = _clip(a.get("movie_id") or "")
        if aspect and pid:
            return both("agent.tool.search_aspect_evidence", aspect=aspect, pid=pid)
        return both("agent.tool.search_aspect_evidence.generic")
    if tool == "get_raw_reviews":
        pid = _clip(a.get("movie_id") or "")
        return both("agent.tool.get_raw_reviews", pid=pid) if pid else both("agent.tool.get_raw_reviews.generic")
    if tool == "extract_id_from_url":
        return both("agent.tool.extract_id_from_url")
    return both("agent.tool.default", tool=tool)
