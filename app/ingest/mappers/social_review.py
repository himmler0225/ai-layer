import re
from app.ingest.mappers.comment import _comment_id


def slugify_movie_id(hint: str) -> str:
    """Slugify movie id."""
    s = (hint or "").lower().strip()
    s = re.sub("[^a-z0-9\\s-]", "", s)
    s = re.sub("\\s+", "-", s).strip("-")
    return s[:80] or "unknown-movie"


def map_social_raw_review(movie_id: str, platform: str, video_id: str, raw: dict) -> dict | None:
    """Map social raw review.

    Args:
        movie_id: (str) Tham số `movie_id`.
        platform: (str) Tham số `platform`.
        video_id: (str) Tham số `video_id`.
        raw: (dict) Tham số `raw`.

    Returns:
        (dict | None) Kết quả trả về."""
    content = (raw.get("content") or raw.get("text") or "").strip()
    if not content:
        return None
    cid = _comment_id(video_id, raw)
    likes = raw.get("likes") or 0
    try:
        likes = int(likes)
    except TypeError, ValueError:
        likes = 0
    return {
        "id": f"{platform}:{video_id}:{cid}",
        "movie_id": movie_id,
        "source": platform,
        "source_video_id": video_id,
        "author": raw.get("author") or "",
        "content": content,
        "rating": None,
        "likes": likes,
        "metadata": {"comment_id": cid},
    }
