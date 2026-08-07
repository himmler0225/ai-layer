from app.ingest.processing.chunking import chunk_transcript
from app.ingest.producer.publisher import publish
from app.ingest.schemas import ROUTING_EMBED
from app.repositories.videos import exists_video, update_transcript, upsert_video


async def handle_transcript_upsert(envelope: dict) -> None:
    """Persist a video's transcript and publish its chunks for embedding.

    Ensures the parent video row exists, stores the transcript text, splits it into
    chunks, and publishes them onto the embed routing key.

    Args:
        envelope: Ingest envelope dict with "video_id"/"platform"/"movie_hint" and a
            "payload" containing "text", "url", and "language".

    Returns:
        None. Does nothing if there is no video id, no text, or no resulting chunks.
    """
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
    hint = envelope.get("movie_hint", "")
    await publish(
        ROUTING_EMBED,
        platform=platform,
        video_id=video_id,
        movie_hint=hint,
        payload={"chunks": [c.model_dump() for c in chunks], "movie_hint": hint},
    )
