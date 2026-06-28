from __future__ import annotations

from typing import Any, Optional


def _as_int(value: Any) -> int:
    """Ép sang int an toàn, lỗi thì trả 0."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _youtube_url(video_id: str) -> str:
    """Tạo URL xem video YouTube."""
    return f"https://www.youtube.com/watch?v={video_id}"


def _tiktok_url(aweme_id: str) -> str:
    """Tạo URL xem video TikTok."""
    return f"https://www.tiktok.com/@_/video/{aweme_id}"


def map_youtube_video(raw: dict) -> Optional[dict]:
    """Chuẩn hóa metadata video YouTube thành row Postgres."""
    video_id = raw.get("video_id") or raw.get("id")
    if not video_id:
        return None
    views = raw.get("view_count") or raw.get("views") or 0
    return {
        "id": str(video_id),
        "platform": "youtube",
        "title": raw.get("title") or "",
        "author": raw.get("channel") or raw.get("author") or "",
        "views": _as_int(views),
        "likes": _as_int(raw.get("likes")),
        "comments_count": _as_int(raw.get("comments_count")),
        "url": _youtube_url(str(video_id)),
        "metadata": {
            "duration": raw.get("length_seconds") or raw.get("duration"),
            "description": (raw.get("description") or "")[:500],
        },
    }


def map_tiktok_video(raw: dict) -> Optional[dict]:
    """Chuẩn hóa metadata video TikTok thành row Postgres."""
    aweme_id = raw.get("aweme_id") or raw.get("id")
    if not aweme_id:
        return None
    stats = raw.get("statistics") or {}
    author = raw.get("author") or {}
    return {
        "id": str(aweme_id),
        "platform": "tiktok",
        "title": raw.get("desc") or raw.get("title") or "",
        "author": author.get("nickname") or raw.get("author_name") or "",
        "views": _as_int(stats.get("play_count") or raw.get("play_count")),
        "likes": _as_int(stats.get("digg_count") or raw.get("likes")),
        "comments_count": _as_int(stats.get("comment_count")),
        "url": _tiktok_url(str(aweme_id)),
        "metadata": {"raw_author": author},
    }
