from app.clients.data_miner._http import get as _get


async def tiktok_search(
    keyword: str,
    cursor: int = 0,
    sort_by: str | None = None,
    date_posted: str | None = None,
    region: str | None = None,
) -> dict:
    params: dict = {"q": keyword, "cursor": cursor}
    if sort_by:
        params["sort_by"] = sort_by
    if date_posted:
        params["date_posted"] = date_posted
    if region:
        params["region"] = region
    return await _get("/api/tiktok/search", params)


async def tiktok_video_info(url: str) -> dict:
    return await _get("/api/tiktok/video-info", {"url": url})


async def tiktok_comments(aweme_id: str, cursor: int = 0, count: int = 20) -> dict:
    return await _get("/api/tiktok/comments", {"aweme_id": aweme_id, "cursor": cursor, "count": count})


async def tiktok_profile(handle: str) -> dict:
    return await _get(f"/api/tiktok/profiles/{handle}")


async def tiktok_transcript(aweme_id: str) -> dict:
    return await _get("/api/tiktok/transcript", {"aweme_id": aweme_id})
