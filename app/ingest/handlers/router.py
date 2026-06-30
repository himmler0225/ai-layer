from __future__ import annotations
import app.ingest.handlers.comments as comments
import app.ingest.handlers.embed as embed
import app.ingest.handlers.summarize as summarize
import app.ingest.handlers.transcript as transcript
import app.ingest.handlers.video as video
from app.exceptions import AiLayerValidationError
from app.ingest.schemas import ROUTING_COMMENTS, ROUTING_EMBED, ROUTING_SUMMARIZE, ROUTING_TRANSCRIPT, ROUTING_VIDEO
_HANDLERS = {ROUTING_VIDEO: video.handle_video_upsert, ROUTING_COMMENTS: comments.handle_comments_upsert, ROUTING_TRANSCRIPT: transcript.handle_transcript_upsert, ROUTING_EMBED: embed.handle_chunks_embed, ROUTING_SUMMARIZE: summarize.handle_movie_summarize}

async def dispatch(envelope: dict) -> None:
    """Dispatch `dispatch` (async).

    Args:
        envelope: (dict) Tham số `envelope`.

    Returns:
        (None) Kết quả trả về."""
    routing_key = envelope.get('routing_key', '')
    handler = _HANDLERS.get(routing_key)
    if not handler:
        raise AiLayerValidationError(f'unknown routing key: {routing_key}')
    await handler(envelope)
