import hashlib


def _comment_id(video_id: str, raw: dict) -> str:
    """Derive a stable id for a raw comment, hashing content if no id is provided.

    Args:
        video_id: Id of the video the comment belongs to, used to salt the hash.
        raw: Raw comment payload from the source API.

    Returns:
        The source-provided comment id as a string, or a "{video_id}:{hash}" id
        derived from the comment content if none is provided.
    """
    cid = raw.get("comment_id") or raw.get("id")
    if cid:
        return str(cid)
    content = raw.get("content") or raw.get("text") or ""
    digest = hashlib.sha256(f"{video_id}:{content}".encode()).hexdigest()[:16]
    return f"{video_id}:{digest}"


def map_comment(video_id: str, raw: dict) -> dict | None:
    """Normalize a raw comment payload into the internal comment dict shape.

    Args:
        video_id: Id of the video the comment belongs to.
        raw: Raw comment payload from the source API.

    Returns:
        A dict with "id", "content", "author", "likes", "published_at", and
        "metadata", or None if the comment has no usable content.
    """
    content = (raw.get("content") or raw.get("text") or "").strip()
    if not content:
        return None
    likes = raw.get("likes") or 0
    try:
        likes = int(likes)
    except TypeError, ValueError:
        likes = 0
    return {
        "id": _comment_id(video_id, raw),
        "content": content,
        "author": raw.get("author") or "",
        "likes": likes,
        "published_at": None,
        "metadata": {"published_time": raw.get("published_time"), "replies_count": raw.get("replies_count")},
    }
