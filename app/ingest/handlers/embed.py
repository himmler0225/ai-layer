from __future__ import annotations
from app.ingest.processing.embeddings import embed_texts
from app.repositories.chunks import upsert_chunks

async def handle_chunks_embed(envelope: dict) -> None:
    """Xử lý chunks embed (async).

    Args:
        envelope: (dict) Tham số `envelope`.

    Returns:
        (None) Kết quả trả về."""
    payload = envelope.get('payload') or {}
    video_id = envelope.get('video_id') or payload.get('video_id')
    platform = envelope.get('platform') or payload.get('platform') or 'youtube'
    raw_chunks = payload.get('chunks') or []
    if not video_id or not raw_chunks:
        return
    texts = [(item.get('content') or '').strip() for item in raw_chunks]
    valid = [(item, text) for item, text in zip(raw_chunks, texts) if text]
    if not valid:
        return
    vectors = await embed_texts([text for _, text in valid])
    movie_hint = payload.get('movie_hint') or envelope.get('movie_hint') or ''
    rows = []
    for (item, text), vector in zip(valid, vectors):
        metadata = dict(item.get('metadata') or {})
        metadata['chunk_type'] = item.get('chunk_type', 'text')
        if movie_hint:
            metadata['movie_hint'] = movie_hint
        rows.append({'id': item['id'], 'video_id': video_id, 'platform': platform, 'content': text, 'embedding': vector, 'metadata': metadata})
    await upsert_chunks(rows)
