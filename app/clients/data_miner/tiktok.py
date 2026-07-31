from app.clients.data_miner._http import get as _get


async def tiktok_search(
    keyword: str,
    cursor: int = 0,
    sort_by: str | None = None,
    date_posted: str | None = None,
    region: str | None = None,
) -> dict:
    """Tiktok search (async).

    Args:
        keyword: (str) Tham số `keyword`.
        cursor: (int, mặc định 0) Tham số `cursor`.
        sort_by: (str | None, mặc định None) Tham số `sort_by`.
        date_posted: (str | None, mặc định None) Tham số `date_posted`.
        region: (str | None, mặc định None) Tham số `region`.

    Returns:
        (dict) Kết quả trả về."""
    params: dict = {"q": keyword, "cursor": cursor}
    if sort_by:
        params["sort_by"] = sort_by
    if date_posted:
        params["date_posted"] = date_posted
    if region:
        params["region"] = region
    return await _get("/api/tiktok/search", params)


async def tiktok_video_info(url: str) -> dict:
    """Tiktok video info (async).

    Args:
        url: (str) Tham số `url`.

    Returns:
        (dict) Kết quả trả về."""
    return await _get("/api/tiktok/video-info", {"url": url})


async def tiktok_comments(aweme_id: str, cursor: int = 0, count: int = 20) -> dict:
    """Tiktok comments (async).

    Args:
        aweme_id: (str) Tham số `aweme_id`.
        cursor: (int, mặc định 0) Tham số `cursor`.
        count: (int, mặc định 20) Tham số `count`.

    Returns:
        (dict) Kết quả trả về."""
    return await _get("/api/tiktok/comments", {"aweme_id": aweme_id, "cursor": cursor, "count": count})


async def tiktok_profile(handle: str) -> dict:
    """Tiktok profile (async).

    Args:
        handle: (str) Tham số `handle`.

    Returns:
        (dict) Kết quả trả về."""
    return await _get(f"/api/tiktok/profiles/{handle}")


async def tiktok_transcript(aweme_id: str) -> dict:
    """Tiktok transcript (async).

    Args:
        aweme_id: (str) Tham số `aweme_id`.

    Returns:
        (dict) Kết quả trả về."""
    return await _get("/api/tiktok/transcript", {"aweme_id": aweme_id})
