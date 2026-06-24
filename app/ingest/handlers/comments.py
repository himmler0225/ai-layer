from __future__ import annotations

from app.ingest.processing.chunking import comment_chunks
from app.ingest.producer import publish
from app.ingest.schemas import ROUTING_EMBED
from app.repositories.comments import insert_comments
from app.repositories.videos import exists_video, upsert_video


async def handle_comments_upsert(envelope: dict) -> None:
    """Ghi comments; comment đạt chất lượng → queue embed."""
    payload = envelope.get("payload") or {}
    video_id = envelope.get("video_id") or payload.get("video_id")
    platform = envelope.get("platform") or payload.get("platform") or "youtube"
    if not video_id:
        return

    raw_comments = payload.get("comments") or []
    if not raw_comments:
        return

    if not await exists_video(video_id):
        await upsert_video(id=video_id, platform=platform, url=payload.get("url", ""))

    await insert_comments(video_id, raw_comments)

    chunks = comment_chunks(video_id, raw_comments)
    if not chunks:
        return

    hint = envelope.get("product_hint", "")
    await publish(
        ROUTING_EMBED,
        platform=platform,
        video_id=video_id,
        product_hint=hint,
        payload={"chunks": [c.model_dump() for c in chunks], "product_hint": hint},
    )
