import asyncio
import uuid
from datetime import UTC, datetime

from app.config.logger import Logger, log_event
from app.ingest.config import INGEST_ENABLED
from app.ingest.schemas import IngestEnvelope

logger = Logger.get(__name__)
_background_tasks: set[asyncio.Task] = set()


async def _run_dispatch(envelope: IngestEnvelope) -> None:
    from app.ingest.handlers.router import dispatch

    try:
        await dispatch(envelope.model_dump())
    except Exception:
        logger.exception(
            log_event(
                "ingest",
                "handler failed",
                routing_key=envelope.routing_key,
                video_id=envelope.video_id or "-",
            )
        )


async def publish(
    routing_key: str, *, platform: str, video_id: str = "", movie_hint: str = "", payload: dict | None = None
) -> None:
    """Schedule in-process ingest handling as a fire-and-forget background task (no broker).

    Builds an IngestEnvelope and runs its dispatch as a background asyncio task
    instead of awaiting it directly, so the agent's response to the user isn't
    blocked — preserving the "publish to a queue" semantics of the previous
    RabbitMQ-based design without an actual broker.

    Args:
        routing_key: One of the ROUTING_* constants selecting the ingest handler.
        platform: Either "youtube" or "tiktok".
        video_id: Optional id of the video the payload relates to.
        movie_hint: Optional free-text movie/product hint.
        payload: Handler-specific payload data.

    Returns:
        None. Does nothing if ingest is disabled via INGEST_ENABLED.
    """
    if not INGEST_ENABLED:
        return
    envelope = IngestEnvelope(
        job_id=str(uuid.uuid4()),
        routing_key=routing_key,
        platform=platform,
        video_id=video_id,
        movie_hint=movie_hint,
        payload=payload or {},
        fetched_at=datetime.now(UTC).isoformat(),
    )
    task = asyncio.create_task(_run_dispatch(envelope), name=f"ingest-{routing_key}")
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
