import asyncio
import uuid
from datetime import UTC, datetime

from app.config.logger import Logger
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
            "[ingest] handler failed key=%s video=%s", envelope.routing_key, envelope.video_id or "-"
        )


async def publish(
    routing_key: str, *, platform: str, video_id: str = "", movie_hint: str = "", payload: dict | None = None
) -> None:
    """Xếp lịch xử lý ingest trong-process (fire-and-forget), không qua broker.

    Chạy dispatch như một background task thay vì await trực tiếp, để không
    chặn phản hồi của agent cho user — giữ đúng ngữ nghĩa "publish vào queue"
    của thiết kế RabbitMQ trước đây.
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
