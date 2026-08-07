from typing import Any

from app.utils.urls import tiktok_url as _tiktok_url, youtube_url as _youtube_url


def _as_int(value: Any) -> int:
    """Best-effort coerce a value to int, defaulting to 0 on failure.

    Args:
        value: Value to coerce (e.g. a count field that may be missing or malformed).

    Returns:
        The coerced int, or 0 if `value` can't be converted.
    """
    try:
        return int(value)
    except TypeError, ValueError:
        return 0


def map_youtube_video(raw: dict) -> dict | None:
    """Normalize a raw YouTube video payload into the internal video dict shape.

    Args:
        raw: Raw video data as returned by the YouTube tool APIs.

    Returns:
        A dict with "id", "platform", "title", "author", "views", "likes",
        "comments_count", "url", and "metadata", or None if the raw payload has
        no usable video id.
    """
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


def map_tiktok_video(raw: dict) -> dict | None:
    """Normalize a raw TikTok video payload into the internal video dict shape.

    Args:
        raw: Raw video data as returned by the TikTok tool APIs.

    Returns:
        A dict with "id", "platform", "title", "author", "views", "likes",
        "comments_count", "url", and "metadata", or None if the raw payload has
        no usable video (aweme) id.
    """
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
