from __future__ import annotations
import app.ingest.handlers.comments as comments
import app.ingest.handlers.embed as embed
import app.ingest.handlers.summarize as summarize
import app.ingest.handlers.transcript as transcript
import app.ingest.handlers.video as video
from app.ingest.schemas import ROUTING_COMMENTS, ROUTING_EMBED, ROUTING_SUMMARIZE, ROUTING_TRANSCRIPT, ROUTING_VIDEO
_HANDLERS = {ROUTING_VIDEO: video.handle_video_upsert, ROUTING_COMMENTS: comments.handle_comments_upsert, ROUTING_TRANSCRIPT: transcript.handle_transcript_upsert, ROUTING_EMBED: embed.handle_chunks_embed, ROUTING_SUMMARIZE: summarize.handle_product_summarize}

async def dispatch(envelope: dict) -> None:
    routing_key = envelope.get('routing_key', '')
    handler = _HANDLERS.get(routing_key)
    if not handler:
        raise ValueError(f'unknown routing key: {routing_key}')
    await handler(envelope)
