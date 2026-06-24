from __future__ import annotations

import hashlib
from typing import Optional


def _comment_id(video_id: str, raw: dict) -> str:
    """Sinh id ổn định cho comment (fallback hash nội dung)."""
    cid = raw.get("comment_id") or raw.get("id")
    if cid:
        return str(cid)
    content = raw.get("content") or raw.get("text") or ""
    digest = hashlib.sha256(f"{video_id}:{content}".encode()).hexdigest()[:16]
    return f"{video_id}:{digest}"


def map_comment(video_id: str, raw: dict) -> Optional[dict]:
    """Chuẩn hóa comment crawl thành row Postgres."""
    content = (raw.get("content") or raw.get("text") or "").strip()
    if not content:
        return None
    likes = raw.get("likes") or 0
    try:
        likes = int(likes)
    except (TypeError, ValueError):
        likes = 0
    return {
        "id": _comment_id(video_id, raw),
        "content": content,
        "author": raw.get("author") or "",
        "likes": likes,
        "published_at": None,
        "metadata": {
            "published_time": raw.get("published_time"),
            "replies_count": raw.get("replies_count"),
        },
    }