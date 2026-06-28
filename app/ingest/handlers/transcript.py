from __future__ import annotations

from app.ingest.processing.chunking import chunk_transcript
from app.ingest.producer import publish
from app.ingest.schemas import ROUTING_EMBED
from app.repositories.videos import (exists_video, update_transcript,
                                     upsert_video)


async def handle_transcript_upsert(envelope: dict) -> None:
    """Ghi transcript đầy đủ rồi chia chunk → queue embed."""
    payload = envelope.get("payload") or {}
    video_id = envelope.get("video_id") or payload.get("video_id")
    platform = envelope.get("platform") or payload.get("platform") or "youtube"
    text = (payload.get("text") or "").strip()
    if not video_id or not text:
        return

    if not await exists_video(video_id):
        await upsert_video(id=video_id, platform=platform, url=payload.get("url", ""))

    await update_transcript(video_id, text)

    chunks = chunk_transcript(video_id, text, language=payload.get("language", ""))
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
