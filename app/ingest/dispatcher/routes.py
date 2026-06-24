from __future__ import annotations

from app.ingest.dispatcher.publish import (
    publish_comments,
    publish_search,
    publish_transcript,
    SEARCH_TOOLS,
)
from app.ingest.mappers import map_tiktok_video, map_youtube_video
from app.ingest.producer import publish
from app.ingest.schemas import ROUTING_VIDEO


async def route_tool(
    tool_name: str,
    inputs: dict,
    data: dict,
    *,
    product_hint: str,
    platform: str,
) -> None:
    """Phân loại tool call → loại job ingest tương ứng."""
    if tool_name in SEARCH_TOOLS:
        await publish_search(inputs, data, platform, product_hint)
        return

    if tool_name in ("youtube_get_detail", "tiktok_video_info"):
        mapped = map_youtube_video(data) if platform == "youtube" else map_tiktok_video(data)
        if mapped:
            await publish(
                ROUTING_VIDEO,
                platform=mapped["platform"],
                video_id=mapped["id"],
                product_hint=product_hint,
                payload={"video": mapped},
            )
        return

    if tool_name == "youtube_get_comments":
        video_id = inputs.get("video_id", "")
        comments = data if isinstance(data, list) else data.get("comments") or data.get("_list") or []
        await publish_comments(video_id, "youtube", comments, product_hint)
        return

    if tool_name == "youtube_get_comments_batch":
        for entry in data.get("results") or []:
            if isinstance(entry, dict):
                await publish_comments(
                    entry.get("video_id", ""),
                    "youtube",
                    entry.get("comments") or [],
                    product_hint,
                )
        return

    if tool_name == "youtube_get_transcript":
        video_id = inputs.get("video_id") or data.get("video_id", "")
        text = data.get("text") or ""
        if video_id and text and data.get("available", True):
            await publish_transcript(video_id, "youtube", text, product_hint, data.get("language", ""))
        return

    if tool_name == "youtube_get_transcript_batch":
        results = data.get("results") or {}
        if isinstance(results, dict):
            for video_id, entry in results.items():
                if entry and isinstance(entry, dict) and entry.get("text"):
                    await publish_transcript(
                        str(video_id), "youtube", entry["text"], product_hint, entry.get("language", "")
                    )
        return

    if tool_name == "tiktok_comments":
        aweme_id = str(inputs.get("aweme_id") or "")
        comments = data.get("comments") or data.get("_list") or []
        if aweme_id and comments:
            await publish_comments(aweme_id, "tiktok", comments, product_hint, url=inputs.get("url", ""))
        return

    if tool_name == "tiktok_transcript":
        aweme_id = str(inputs.get("aweme_id") or data.get("aweme_id") or "")
        text = data.get("text") or data.get("transcript") or ""
        if isinstance(data.get("segments"), list) and not text:
            text = " ".join(
                seg.get("text", "") if isinstance(seg, dict) else str(seg)
                for seg in data["segments"]
            ).strip()
        if aweme_id and text:
            await publish_transcript(aweme_id, "tiktok", text, product_hint, data.get("language", ""))