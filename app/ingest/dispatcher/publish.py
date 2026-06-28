from __future__ import annotations

from typing import Any

from app.ingest.mappers import (extract_search_query, map_comment,
                                map_tiktok_video, map_youtube_video,
                                video_list)
from app.ingest.producer import publish
from app.ingest.schemas import (ROUTING_COMMENTS, ROUTING_TRANSCRIPT,
                                ROUTING_VIDEO)

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
    """Chọn mapper YouTube hoặc TikTok theo nền tảng."""
    if platform == "youtube":
        return map_youtube_video(raw)
    return map_tiktok_video(raw)


async def publish_videos(
    videos: list[dict],
    *,
    platform: str,
    product_hint: str,
    search_cache: dict | None = None,
) -> None:
    """Gửi từng video lên queue; job đầu có thể kèm cache search."""
    for index, raw in enumerate(videos):
        mapped = _map_video(raw, platform)
        if not mapped:
            continue
        payload: dict[str, Any] = {"video": mapped}
        if search_cache and index == 0:
            payload["search_cache"] = search_cache
        await publish(
            ROUTING_VIDEO,
            platform=mapped["platform"],
            video_id=mapped["id"],
            product_hint=product_hint,
            payload=payload,
        )


async def publish_search(
    inputs: dict, data: dict, platform: str, product_hint: str
) -> None:
    """Sau tool search — lưu video và cache video_ids theo từ khóa."""
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

    await publish_videos(
        videos, platform=platform, product_hint=product_hint, search_cache=search_cache
    )


async def publish_comments(
    video_id: str,
    platform: str,
    comments: list[dict],
    product_hint: str,
    url: str = "",
) -> None:
    """Gửi batch comment đã chuẩn hóa của một video."""
    mapped = [map_comment(video_id, raw) for raw in comments if isinstance(raw, dict)]
    mapped = [item for item in mapped if item]
    if not mapped:
        return
    await publish(
        ROUTING_COMMENTS,
        platform=platform,
        video_id=video_id,
        product_hint=product_hint,
        payload={
            "video_id": video_id,
            "platform": platform,
            "comments": mapped,
            "url": url,
        },
    )


async def publish_transcript(
    video_id: str,
    platform: str,
    text: str,
    product_hint: str,
    language: str = "",
) -> None:
    """Gửi transcript để worker ghi DB và chia chunk."""
    if not video_id or not text:
        return
    await publish(
        ROUTING_TRANSCRIPT,
        platform=platform,
        video_id=video_id,
        product_hint=product_hint,
        payload={
            "video_id": video_id,
            "platform": platform,
            "text": text,
            "language": language,
        },
    )
