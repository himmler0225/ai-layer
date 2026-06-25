from __future__ import annotations

"""Map comment YouTube/TikTok → row bảng raw_reviews (L3)."""

import re

from app.ingest.mappers.comment import _comment_id


def slugify_product_id(hint: str) -> str:
    """
    Đổi tên sản phẩm từ chat thành product_id cố định.

    Ví dụ: 'Review iPhone 17 Pro' → 'iphone-17-pro'.
    Dùng làm khóa chung cho products, raw_reviews, aspect_*.
    """
    s = (hint or "").lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s[:80] or "unknown-product"


def map_social_raw_review(product_id: str, platform: str, video_id: str, raw: dict) -> dict | None:
    """
    Một comment crawl (dict từ data-miner) → một row L3 (raw_reviews).

    - Lấy content/text; trả None nếu rỗng.
    - id = '{platform}:{video_id}:{comment_id}'.
    - Gắn product_id, likes, author, source_video_id.
    """
    content = (raw.get("content") or raw.get("text") or "").strip()
    if not content:
        return None
    cid = _comment_id(video_id, raw)
    likes = raw.get("likes") or 0
    try:
        likes = int(likes)
    except (TypeError, ValueError):
        likes = 0
    return {
        "id": f"{platform}:{video_id}:{cid}",
        "product_id": product_id,
        "source": platform,
        "source_video_id": video_id,
        "author": raw.get("author") or "",
        "content": content,
        "rating": None,
        "likes": likes,
        "metadata": {"comment_id": cid},
    }
