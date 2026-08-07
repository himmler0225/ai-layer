from typing import Any
from app.ingest.mappers.comment import map_comment
from app.ingest.mappers.unwrap import extract_search_query, video_list
from app.ingest.mappers.video import map_tiktok_video, map_youtube_video
from app.ingest.producer.publisher import publish
from app.ingest.schemas import ROUTING_COMMENTS, ROUTING_TRANSCRIPT, ROUTING_VIDEO

SEARCH_TOOLS = frozenset(
    {
        "youtube_search",
        "youtube_get_by_topic",
        "youtube_get_shorts",
        "youtube_get_live",
        "youtube_get_by_region",
        "youtube_get_channel_videos",
        "tiktok_search",
    }
)


def _map_video(raw: dict, platform: str) -> dict | None:
    """Map a raw video payload to the normalized video dict for the given platform.

    Args:
        raw: Raw video data as returned by the source API.
        platform: Either "youtube" or "tiktok"; selects which mapper to use.

    Returns:
        The normalized video dict, or None if the raw payload has no usable id.
    """
    if platform == "youtube":
        return map_youtube_video(raw)
    return map_tiktok_video(raw)


async def publish_videos(
    videos: list[dict], *, platform: str, movie_hint: str, search_cache: dict | None = None
) -> None:
    """Map and publish a batch of raw videos onto the video ingest routing key.

    Args:
        videos: Raw video payloads from the source API.
        platform: Either "youtube" or "tiktok"; selects which mapper to use.
        movie_hint: Free-text movie/product hint to attach to each published envelope.
        search_cache: Optional search-cache payload (query, platform, video ids)
            attached only to the first successfully mapped video.

    Returns:
        None. Videos that fail to map are silently skipped.
    """
    for index, raw in enumerate(videos):
        mapped = _map_video(raw, platform)
        if not mapped:
            continue
        payload: dict[str, Any] = {"video": mapped}
        if search_cache and index == 0:
            payload["search_cache"] = search_cache
        await publish(
            ROUTING_VIDEO, platform=mapped["platform"], video_id=mapped["id"], movie_hint=movie_hint, payload=payload
        )


async def publish_search(inputs: dict, data: dict, platform: str, movie_hint: str) -> None:
    """Extract videos from a search-tool result and publish them, caching the query.

    Args:
        inputs: Original tool call arguments, used to recover the search keyword/query.
        data: Unwrapped tool result data expected to contain a list of videos.
        platform: Either "youtube" or "tiktok".
        movie_hint: Free-text movie/product hint to attach to published envelopes.

    Returns:
        None. Does nothing if no videos are found in `data`.
    """
    videos = video_list(data)
    if not videos:
        return
    query = extract_search_query(inputs)
    search_cache = None
    if query:
        ids = []
        for raw in videos:
            mapped = _map_video(raw, platform)
            if mapped:
                ids.append(mapped["id"])
        if ids:
            search_cache = {"query": query, "platform": platform, "video_ids": ids}
    await publish_videos(videos, platform=platform, movie_hint=movie_hint, search_cache=search_cache)


async def publish_comments(video_id: str, platform: str, comments: list[dict], movie_hint: str, url: str = "") -> None:
    """Map raw comments for a video and publish them onto the comments routing key.

    Args:
        video_id: Id of the video the comments belong to.
        platform: Either "youtube" or "tiktok".
        comments: Raw comment payloads from the source API.
        movie_hint: Free-text movie/product hint to attach to the published envelope.
        url: Optional source URL for the video, forwarded in the payload.

    Returns:
        None. Does nothing if no comment maps to a valid entry.
    """
    mapped = [map_comment(video_id, raw) for raw in comments if isinstance(raw, dict)]
    mapped = [item for item in mapped if item]
    if not mapped:
        return
    await publish(
        ROUTING_COMMENTS,
        platform=platform,
        video_id=video_id,
        movie_hint=movie_hint,
        payload={"video_id": video_id, "platform": platform, "comments": mapped, "url": url},
    )


async def publish_transcript(video_id: str, platform: str, text: str, movie_hint: str, language: str = "") -> None:
    """Publish a video transcript onto the transcript routing key.

    Args:
        video_id: Id of the video the transcript belongs to.
        platform: Either "youtube" or "tiktok".
        text: Full transcript text.
        movie_hint: Free-text movie/product hint to attach to the published envelope.
        language: Optional transcript language code, forwarded in the payload.

    Returns:
        None. Does nothing if `video_id` or `text` is empty.
    """
    if not video_id or not text:
        return
    await publish(
        ROUTING_TRANSCRIPT,
        platform=platform,
        video_id=video_id,
        movie_hint=movie_hint,
        payload={"video_id": video_id, "platform": platform, "text": text, "language": language},
    )
