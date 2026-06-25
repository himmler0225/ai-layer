from __future__ import annotations

from app.ingest.handlers import comments, embed, transcript, video, summarize
from app.ingest.schemas import (
    ROUTING_COMMENTS,
    ROUTING_EMBED,
    ROUTING_TRANSCRIPT,
    ROUTING_VIDEO,
    ROUTING_SUMMARIZE,
)

_HANDLERS = {
    ROUTING_VIDEO: video.handle_video_upsert,
    ROUTING_COMMENTS: comments.handle_comments_upsert,
    ROUTING_TRANSCRIPT: transcript.handle_transcript_upsert,
    ROUTING_EMBED: embed.handle_chunks_embed,
    ROUTING_SUMMARIZE: summarize.handle_product_summarize,
}


async def dispatch(envelope: dict) -> None:
    """Chọn handler xử lý theo loại job trong envelope."""
    routing_key = envelope.get("routing_key", "")
    handler = _HANDLERS.get(routing_key)
    if not handler:
        raise ValueError(f"unknown routing key: {routing_key}")
    await handler(envelope)
