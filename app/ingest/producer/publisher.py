import uuid
from datetime import datetime, UTC
import aio_pika
from app.ingest.config import INGEST_ENABLED, RABBITMQ_URL
from app.config.logger import Logger
from app.ingest.broker.connection import close_broker, get_exchange
from app.ingest.broker.topology import declare_topology
from app.ingest.schemas import IngestEnvelope

logger = Logger.get(__name__)
_ready = False


async def init_producer() -> None:
    """Khởi tạo producer (async).

    Returns:
        (None) Kết quả trả về."""
    global _ready
    if not INGEST_ENABLED or not RABBITMQ_URL:
        logger.info("[ingest] producer disabled")
        return
    try:
        await declare_topology()
        await get_exchange()
        _ready = True
        logger.info("[ingest] producer ready")
    except Exception as exc:
        _ready = False
        logger.warning("[ingest] producer init failed: %s", exc)


async def close_producer() -> None:
    """Đóng producer (async).

    Returns:
        (None) Kết quả trả về."""
    global _ready
    _ready = False
    await close_broker()


def _enabled() -> bool:
    """(Nội bộ) Enabled `_enabled`.

    Returns:
        (bool) Kết quả trả về."""
    return INGEST_ENABLED and bool(RABBITMQ_URL) and _ready


async def publish(
    routing_key: str, *, platform: str, video_id: str = "", movie_hint: str = "", payload: dict | None = None
) -> None:
    """Xuất bản `publish` (async).

    Args:
        routing_key: (str) Tham số `routing_key`.
        platform: (str) Tham số `platform`.
        video_id: (str, mặc định '') Tham số `video_id`.
        movie_hint: (str, mặc định '') Tham số `movie_hint`.
        payload: (Optional[dict], mặc định None) Tham số `payload`.

    Returns:
        (None) Kết quả trả về."""
    if not _enabled():
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
    try:
        exchange = await get_exchange()
        await exchange.publish(
            aio_pika.Message(
                body=envelope.model_dump_json().encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=routing_key,
        )
        logger.debug("[ingest] published key=%s video=%s", routing_key, video_id or "-")
    except Exception as exc:
        logger.warning("[ingest] publish failed key=%s: %s", routing_key, exc)
