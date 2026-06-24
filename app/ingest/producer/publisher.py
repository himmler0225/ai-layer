from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import aio_pika

import app.config.settings as _cfg
from app.config.logger import Logger
from app.ingest.broker import close_broker, declare_topology, get_exchange
from app.ingest.schemas import IngestEnvelope

logger = Logger.get(__name__)
_ready = False


async def init_producer() -> None:
    """Khởi tạo producer khi API bật."""
    global _ready
    if not _cfg.INGEST_ENABLED or not _cfg.RABBITMQ_URL:
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
    """Đóng kết nối broker khi API tắt."""
    global _ready
    _ready = False
    await close_broker()


def _enabled() -> bool:
    """Kiểm tra producer đã sẵn sàng gửi job chưa."""
    return _cfg.INGEST_ENABLED and bool(_cfg.RABBITMQ_URL) and _ready


async def publish(
    routing_key: str,
    *,
    platform: str,
    video_id: str = "",
    product_hint: str = "",
    payload: Optional[dict] = None,
) -> None:
    """Gửi một job ingest lên RabbitMQ."""
    if not _enabled():
        return

    envelope = IngestEnvelope(
        job_id=str(uuid.uuid4()),
        routing_key=routing_key,
        platform=platform,  # type: ignore[arg-type]
        video_id=video_id,
        product_hint=product_hint,
        payload=payload or {},
        fetched_at=datetime.now(timezone.utc).isoformat(),
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