"""Nhãn trạng thái cụ thể cho SSE tool_start — hiển thị trên UI chat."""

from __future__ import annotations

import json
from typing import Any


def _clip(text: str, n: int = 48) -> str:
    s = (text or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _ids(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str):
        return [x.strip() for x in raw.split(",") if x.strip()]
    return []


def _parse_args(arguments: str | None) -> dict:
    if not arguments:
        return {}
    try:
        parsed = json.loads(arguments)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def tool_status(tool: str, args: dict) -> tuple[str, str]:
    """Trả (tiếng Việt, English) cho một tool call."""
    a = args or {}

    if tool == "youtube_search":
        q = _clip(a.get("keyword") or a.get("query") or "")
        return (
            f"Đang tìm video YouTube: «{q}»…" if q else "Đang tìm video trên YouTube…",
            f'Searching YouTube for "{q}"…' if q else "Searching YouTube…",
        )

    if tool == "youtube_get_comments":
        vid = a.get("video_id") or ""
        return (
            (
                f"Đang lấy bình luận video {vid}…"
                if vid
                else "Đang lấy bình luận YouTube…"
            ),
            f"Fetching comments for {vid}…" if vid else "Fetching YouTube comments…",
        )

    if tool == "youtube_get_comments_batch":
        ids = _ids(a.get("video_ids"))
        n = len(ids)
        if n == 1:
            return (
                f"Đang lấy bình luận video {ids[0]}…",
                f"Fetching comments for {ids[0]}…",
            )
        if n > 1:
            return (
                f"Đang lấy bình luận {n} video YouTube ({ids[0]}…)…",
                f"Fetching comments from {n} YouTube videos…",
            )
        return (
            "Đang lấy bình luận nhiều video YouTube…",
            "Fetching YouTube comments (batch)…",
        )

    if tool in ("youtube_get_transcript",):
        vid = a.get("video_id") or ""
        return (
            (
                f"Đang lấy transcript video {vid}…"
                if vid
                else "Đang lấy transcript YouTube…"
            ),
            (
                f"Fetching transcript for {vid}…"
                if vid
                else "Fetching YouTube transcript…"
            ),
        )

    if tool == "youtube_get_transcript_batch":
        ids = _ids(a.get("video_ids"))
        n = len(ids)
        if n == 1:
            return (
                f"Đang lấy transcript video {ids[0]}…",
                f"Fetching transcript for {ids[0]}…",
            )
        if n > 1:
            return (
                f"Đang lấy transcript {n} video ({ids[0]}…)…",
                f"Fetching transcripts for {n} videos…",
            )
        return "Đang lấy transcript nhiều video…", "Fetching YouTube transcripts…"

    if tool == "youtube_get_detail":
        vid = a.get("video_id") or ""
        return (
            f"Đang xem chi tiết video {vid}…" if vid else "Đang xem chi tiết video…",
            f"Loading video details {vid}…" if vid else "Loading video details…",
        )

    if tool == "youtube_get_by_topic":
        topic = a.get("topic") or ""
        return (
            (
                f"Đang lấy video chủ đề {topic}…"
                if topic
                else "Đang lấy video theo chủ đề…"
            ),
            f"Browsing YouTube topic {topic}…" if topic else "Browsing by topic…",
        )

    if tool == "youtube_get_by_region":
        q = _clip(a.get("query") or "")
        gl = a.get("gl") or ""
        return (
            f"Đang tìm video {gl}: «{q}»…" if q else f"Đang tìm video khu vực {gl}…",
            f"Searching {gl}: {q}…" if q else f"Searching region {gl}…",
        )

    if tool == "youtube_get_channel_info":
        ch = _clip(a.get("channel_id") or "")
        return (
            f"Đang xem kênh {ch}…" if ch else "Đang xem thông tin kênh…",
            f"Loading channel {ch}…" if ch else "Loading channel info…",
        )

    if tool == "youtube_get_channel_videos":
        ch = _clip(a.get("channel_id") or "")
        return (
            f"Đang lấy video của kênh {ch}…" if ch else "Đang lấy video kênh…",
            f"Fetching videos from {ch}…" if ch else "Fetching channel videos…",
        )

    if tool == "tiktok_search":
        q = _clip(a.get("keyword") or "")
        return (
            f"Đang tìm TikTok: «{q}»…" if q else "Đang tìm video TikTok…",
            f'Searching TikTok for "{q}"…' if q else "Searching TikTok…",
        )

    if tool == "tiktok_comments":
        aweme = a.get("aweme_id") or ""
        return (
            (
                f"Đang lấy bình luận TikTok ({aweme})…"
                if aweme
                else "Đang lấy bình luận TikTok…"
            ),
            (
                f"Fetching TikTok comments ({aweme})…"
                if aweme
                else "Fetching TikTok comments…"
            ),
        )

    if tool == "tiktok_transcript":
        aweme = a.get("aweme_id") or ""
        return (
            (
                f"Đang lấy transcript TikTok ({aweme})…"
                if aweme
                else "Đang lấy transcript TikTok…"
            ),
            (
                f"Fetching TikTok transcript ({aweme})…"
                if aweme
                else "Fetching TikTok transcript…"
            ),
        )

    if tool == "tiktok_video_info":
        url = _clip(a.get("url") or "")
        return (
            (
                f"Đang xem video TikTok…"
                if not url
                else "Đang xem thông tin video TikTok…"
            ),
            "Loading TikTok video…",
        )

    if tool == "tiktok_profile":
        handle = a.get("handle") or ""
        return (
            f"Đang xem profile @{handle}…" if handle else "Đang xem profile TikTok…",
            f"Loading @{handle}…" if handle else "Loading TikTok profile…",
        )

    if tool == "search_product_summary":
        pid = _clip(a.get("product_id") or "")
        return (
            (
                f"Đang đọc tổng quan review «{pid}»…"
                if pid
                else "Đang đọc tổng quan review…"
            ),
            f"Reading saved summary for {pid}…" if pid else "Reading product summary…",
        )

    if tool == "search_aspect_evidence":
        aspect = a.get("aspect") or ""
        pid = _clip(a.get("product_id") or "")
        if aspect and pid:
            return (
                f"Đang tìm chi tiết {aspect} — {pid}…",
                f"Searching {aspect} evidence for {pid}…",
            )
        return "Đang tìm chi tiết review…", "Searching review details…"

    if tool == "get_raw_reviews":
        pid = _clip(a.get("product_id") or "")
        return (
            f"Đang lấy review gốc «{pid}»…" if pid else "Đang lấy review gốc…",
            f"Fetching raw reviews for {pid}…" if pid else "Fetching raw reviews…",
        )

    if tool == "extract_id_from_url":
        return "Đang phân tích link video…", "Parsing video URL…"

    # fallback
    return f"Đang chạy {tool}…", f"Running {tool}…"
