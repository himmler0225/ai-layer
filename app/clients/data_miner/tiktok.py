from app.clients.data_miner._http import get as _get


async def tiktok_search(
    keyword: str,
    cursor: int = 0,
    sort_by: str | None = None,
    date_posted: str | None = None,
    region: str | None = None,
) -> dict:
    """Search TikTok videos by keyword.

    Args:
        keyword: Search text.
        cursor: Pagination cursor; `0` for the first page.
        sort_by: Optional sort order (e.g. relevance, date).
        date_posted: Optional recency filter for when videos were posted.
        region: Optional region/country code filter.

    Returns:
        The data-miner TikTok search response (dict)."""
    params: dict = {"q": keyword, "cursor": cursor}
    if sort_by:
        params["sort_by"] = sort_by
    if date_posted:
        params["date_posted"] = date_posted
    if region:
        params["region"] = region
    return await _get("/api/tiktok/search", params)


async def tiktok_video_info(url: str) -> dict:
    """Fetch metadata for a single TikTok video by its URL.

    Args:
        url: The TikTok video URL.

    Returns:
        The data-miner video info response (dict)."""
    return await _get("/api/tiktok/video-info", {"url": url})


async def tiktok_comments(aweme_id: str, cursor: int = 0, count: int = 20) -> dict:
    """Fetch comments for a TikTok video.

    Args:
        aweme_id: The TikTok video's aweme id.
        cursor: Pagination cursor; `0` for the first page.
        count: Maximum number of comments to fetch.

    Returns:
        The data-miner comments response (dict)."""
    return await _get("/api/tiktok/comments", {"aweme_id": aweme_id, "cursor": cursor, "count": count})


async def tiktok_profile(handle: str) -> dict:
    """Fetch a TikTok user profile by handle.

    Args:
        handle: The TikTok username/handle.

    Returns:
        The data-miner profile response (dict)."""
    return await _get(f"/api/tiktok/profiles/{handle}")


async def tiktok_transcript(aweme_id: str) -> dict:
    """Fetch the spoken-audio transcript for a TikTok video.

    Args:
        aweme_id: The TikTok video's aweme id.

    Returns:
        The data-miner transcript response (dict)."""
    return await _get("/api/tiktok/transcript", {"aweme_id": aweme_id})
