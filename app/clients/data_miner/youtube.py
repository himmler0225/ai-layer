from app.clients.data_miner._http import get as _get


async def search_youtube(query: str, max_results: int = 10, sort: str = "relevance") -> dict:
    return await _get("/api/videos/search", {"q": query, "max_results": max_results, "sort": sort})


async def get_video_detail(video_id: str) -> dict:
    return await _get(f"/api/videos/{video_id}")


async def get_video_comments(video_id: str, max_comments: int = 20, sort: str = "newest") -> dict:
    return await _get(f"/api/videos/{video_id}/comments", {"limit": max_comments, "sort": sort})


async def get_video_comments_batch(video_ids: list, max_per_video: int = 20, sort: str = "top") -> dict:
    return await _get(
        "/api/videos/comments/batch",
        {"video_ids": ",".join(video_ids), "limit": max_per_video, "sort": sort},
    )


async def get_video_transcript(video_id: str) -> dict:
    return await _get(f"/api/videos/{video_id}/transcript")


async def get_video_transcript_batch(video_ids: list) -> dict:
    return await _get("/api/videos/transcript/batch", {"video_ids": ",".join(video_ids)})


async def get_trending(max_results: int = 20) -> dict:
    """Top-viewed YouTube search — data-miner không có route `/api/videos/trending`."""
    return await search_youtube("trending", max_results=max_results, sort="view_count")


async def get_shorts(max_results: int = 20) -> dict:
    return await _get("/api/videos/shorts", {"limit": max_results})


async def get_live(query: str = "", max_results: int = 20) -> dict:
    return await _get("/api/videos/live", {"q": query, "limit": max_results})


async def get_by_region(gl: str, hl: str, query: str, max_results: int = 20) -> dict:
    return await _get("/api/videos/location", {"gl": gl, "hl": hl, "query": query, "max_results": max_results})


async def get_by_topic(topic: str, max_results: int = 20) -> dict:
    return await _get("/api/videos/by-topic", {"topic": topic, "limit": max_results})


async def get_channel_info(channel_id: str) -> dict:
    return await _get(f"/api/channels/{channel_id}")


async def get_channel_videos(channel_id: str, max_results: int = 30) -> dict:
    return await _get(f"/api/channels/{channel_id}/videos", {"limit": max_results})


async def get_channel_playlists(channel_id: str) -> dict:
    return await _get(f"/api/channels/{channel_id}/playlists")


async def get_playlist_videos(playlist_id: str, max_results: int = 30) -> dict:
    return await _get(f"/api/playlists/{playlist_id}/videos", {"limit": max_results})
