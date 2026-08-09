from app.ingest.processing.embeddings import embed_texts
from app.repositories.chunks import upsert_chunks


async def handle_chunks_embed(envelope: dict) -> None:
    """Embed the chunks in an envelope's payload and upsert them into chunk storage.

    Filters out chunks with empty content, computes embedding vectors for the rest,
    attaches chunk type and (if present) movie hint to each chunk's metadata, then
    persists the resulting rows.

    Args:
        envelope: Ingest envelope dict with "video_id"/"platform"/"movie_hint" and a
            "payload" containing "chunks" (list of chunk dicts with id/content/
            chunk_type/metadata).

    Returns:
        None. Does nothing if there is no video id or no non-empty chunks.
    """
    payload = envelope.get("payload") or {}
    video_id = envelope.get("video_id") or payload.get("video_id")
    platform = envelope.get("platform") or payload.get("platform") or "youtube"
    raw_chunks = payload.get("chunks") or []
    if not video_id or not raw_chunks:
        return
    texts = [(item.get("content") or "").strip() for item in raw_chunks]
    valid = [(item, text) for item, text in zip(raw_chunks, texts, strict=True) if text]
    if not valid:
        return
    vectors = await embed_texts([text for _, text in valid])
    movie_hint = payload.get("movie_hint") or envelope.get("movie_hint") or ""
    rows = []
    for (item, text), vector in zip(valid, vectors):
        metadata = dict(item.get("metadata") or {})
        metadata["chunk_type"] = item.get("chunk_type", "text")
        if movie_hint:
            metadata["movie_hint"] = movie_hint
        rows.append(
            {
                "id": item["id"],
                "video_id": video_id,
                "platform": platform,
                "content": text,
                "embedding": vector,
                "metadata": metadata,
            }
        )
    await upsert_chunks(rows)
