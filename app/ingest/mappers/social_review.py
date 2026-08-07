import re
from app.ingest.mappers.comment import _comment_id


def slugify_movie_id(hint: str) -> str:
    """Convert a free-text movie/product hint into a URL/id-safe slug.

    Lowercases the input, strips characters other than letters/digits/spaces/hyphens,
    collapses whitespace into hyphens, and truncates to 80 characters.

    Args:
        hint: Free-text movie/product name or hint.

    Returns:
        The slugified string, or "unknown-movie" if the result is empty.
    """
    s = (hint or "").lower().strip()
    s = re.sub("[^a-z0-9\\s-]", "", s)
    s = re.sub("\\s+", "-", s).strip("-")
    return s[:80] or "unknown-movie"


def map_social_raw_review(movie_id: str, platform: str, video_id: str, raw: dict) -> dict | None:
    """Normalize a raw comment into a raw-review row for the movie RAG pipeline.

    Args:
        movie_id: Slugified id of the movie/product this review is being attributed to.
        platform: Either "youtube" or "tiktok".
        video_id: Id of the video the comment was posted on.
        raw: Raw comment payload from the source API.

    Returns:
        A dict with "id", "movie_id", "source", "source_video_id", "author",
        "content", "rating", "likes", and "metadata", or None if the comment has
        no usable content.
    """
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
