from app.clients.data_miner._http import get as _get


async def search_youtube(query: str, max_results: int = 10, sort: str = "relevance") -> dict:
    """Search YouTube videos by keyword.

    Args:
        query: Search text.
        max_results: Maximum number of results to return.
        sort: Sort order (e.g. `"relevance"`, `"view_count"`).

    Returns:
        The data-miner video search response (dict)."""
    return await _get("/api/videos/search", {"q": query, "max_results": max_results, "sort": sort})


async def get_video_detail(video_id: str) -> dict:
    """Fetch metadata for a single YouTube video.

    Args:
        video_id: The YouTube video id.

    Returns:
        The data-miner video detail response (dict)."""
    return await _get(f"/api/videos/{video_id}")


async def get_video_comments(video_id: str, max_comments: int = 20, sort: str = "newest") -> dict:
    """Fetch comments for a single YouTube video.

    Args:
        video_id: The YouTube video id.
        max_comments: Maximum number of comments to fetch (sent as `limit`).
        sort: Sort order (e.g. `"newest"`, `"top"`).

    Returns:
        The data-miner comments response (dict)."""
    return await _get(f"/api/videos/{video_id}/comments", {"limit": max_comments, "sort": sort})


async def get_video_comments_batch(video_ids: list, max_per_video: int = 20, sort: str = "top") -> dict:
    """Fetch comments for multiple YouTube videos in one request.

    Args:
        video_ids: List of YouTube video ids (joined with commas for the
            request).
        max_per_video: Maximum number of comments to fetch per video.
        sort: Sort order (e.g. `"top"`, `"newest"`).

    Returns:
        The data-miner batch comments response (dict)."""
    return await _get(
        "/api/videos/comments/batch",
        {"video_ids": ",".join(video_ids), "limit": max_per_video, "sort": sort},
    )


async def get_video_transcript(video_id: str) -> dict:
    """Fetch the transcript/captions for a single YouTube video.

    Args:
        video_id: The YouTube video id.

    Returns:
        The data-miner transcript response (dict)."""
    return await _get(f"/api/videos/{video_id}/transcript")


async def get_video_transcript_batch(video_ids: list) -> dict:
    """Fetch transcripts for multiple YouTube videos in one request.

    Args:
        video_ids: List of YouTube video ids (joined with commas for the
            request).

    Returns:
        The data-miner batch transcript response (dict)."""
    return await _get("/api/videos/transcript/batch", {"video_ids": ",".join(video_ids)})


async def get_trending(max_results: int = 20) -> dict:
    """Approximate a "trending" feed via a view-count-sorted search, since
    data-miner has no dedicated `/api/videos/trending` route."""
    return await search_youtube("trending", max_results=max_results, sort="view_count")


async def get_shorts(max_results: int = 20) -> dict:
    """Fetch a list of YouTube Shorts.

    Args:
        max_results: Maximum number of results to return.

    Returns:
        The data-miner shorts response (dict)."""
    return await _get("/api/videos/shorts", {"limit": max_results})


async def get_live(query: str = "", max_results: int = 20) -> dict:
    """Fetch currently live YouTube streams, optionally filtered by keyword.

    Args:
        query: Optional search text; empty string returns unfiltered results.
        max_results: Maximum number of results to return.

    Returns:
        The data-miner live streams response (dict)."""
    return await _get("/api/videos/live", {"q": query, "limit": max_results})


async def get_by_region(gl: str, hl: str, query: str, max_results: int = 20) -> dict:
    """Search YouTube videos scoped to a geographic region/language.

    Args:
        gl: Google/YouTube region code (e.g. `"US"`, `"VN"`).
        hl: Interface/host language code (e.g. `"en"`, `"vi"`).
        query: Search text.
        max_results: Maximum number of results to return.

    Returns:
        The data-miner region search response (dict)."""
    return await _get("/api/videos/location", {"gl": gl, "hl": hl, "query": query, "max_results": max_results})


async def get_by_topic(topic: str, max_results: int = 20) -> dict:
    """Fetch YouTube videos related to a given topic.

    Args:
        topic: The topic identifier/keyword to filter by.
        max_results: Maximum number of results to return (sent as `limit`).

    Returns:
        The data-miner by-topic response (dict)."""
    return await _get("/api/videos/by-topic", {"topic": topic, "limit": max_results})


async def get_channel_info(channel_id: str) -> dict:
    """Fetch metadata for a single YouTube channel.

    Args:
        channel_id: The YouTube channel id.

    Returns:
        The data-miner channel info response (dict)."""
    return await _get(f"/api/channels/{channel_id}")


async def get_channel_videos(channel_id: str, max_results: int = 30) -> dict:
    """List videos published by a YouTube channel.

    Args:
        channel_id: The YouTube channel id.
        max_results: Maximum number of results to return (sent as `limit`).

    Returns:
        The data-miner channel videos response (dict)."""
    return await _get(f"/api/channels/{channel_id}/videos", {"limit": max_results})


async def get_channel_playlists(channel_id: str) -> dict:
    """List playlists belonging to a YouTube channel.

    Args:
        channel_id: The YouTube channel id.

    Returns:
        The data-miner channel playlists response (dict)."""
    return await _get(f"/api/channels/{channel_id}/playlists")


async def get_playlist_videos(playlist_id: str, max_results: int = 30) -> dict:
    """List videos contained in a YouTube playlist.

    Args:
        playlist_id: The YouTube playlist id.
        max_results: Maximum number of results to return (sent as `limit`).

    Returns:
        The data-miner playlist videos response (dict)."""
    return await _get(f"/api/playlists/{playlist_id}/videos", {"limit": max_results})
