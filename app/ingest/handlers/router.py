import app.ingest.handlers.comments as comments
import app.ingest.handlers.embed as embed
import app.ingest.handlers.summarize as summarize
import app.ingest.handlers.transcript as transcript
import app.ingest.handlers.video as video
from app.exceptions import AiLayerValidationError
from app.ingest.schemas import ROUTING_COMMENTS, ROUTING_EMBED, ROUTING_SUMMARIZE, ROUTING_TRANSCRIPT, ROUTING_VIDEO

_HANDLERS = {
    ROUTING_VIDEO: video.handle_video_upsert,
    ROUTING_COMMENTS: comments.handle_comments_upsert,
    ROUTING_TRANSCRIPT: transcript.handle_transcript_upsert,
    ROUTING_EMBED: embed.handle_chunks_embed,
    ROUTING_SUMMARIZE: summarize.handle_movie_summarize,
}


async def dispatch(envelope: dict) -> None:
    """Look up and invoke the ingest handler matching an envelope's routing key.

    Args:
        envelope: Ingest envelope dict; must contain a "routing_key" matching one
            of the registered ROUTING_* constants.

    Returns:
        None.

    Raises:
        AiLayerValidationError: If the routing key has no registered handler.
    """
    routing_key = envelope.get("routing_key", "")
    handler = _HANDLERS.get(routing_key)
    if not handler:
        raise AiLayerValidationError(f"unknown routing key: {routing_key}")
    await handler(envelope)
