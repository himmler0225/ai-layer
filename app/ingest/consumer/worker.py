import asyncio
import json
from aio_pika.abc import AbstractIncomingMessage
from app.config.logger import Logger
from app.exceptions import AiLayerValidationError
from app.ingest.broker.connection import get_channel
from app.ingest.broker.topology import declare_topology
from app.ingest.handlers.router import dispatch
from app.ingest.schemas import QUEUE_COMMENTS, QUEUE_EMBED, QUEUE_SUMMARIZE, QUEUE_TRANSCRIPT, QUEUE_VIDEO

logger = Logger.get(__name__)
_QUEUES = (QUEUE_VIDEO, QUEUE_COMMENTS, QUEUE_TRANSCRIPT, QUEUE_EMBED, QUEUE_SUMMARIZE)
_MAX_RETRIES = 3


def _retry_count(message: AbstractIncomingMessage) -> int:
    """(Nội bộ) Retry count.

    Args:
        message: (AbstractIncomingMessage) Tham số `message`.

    Returns:
        (int) Kết quả trả về."""
    deaths = message.headers.get("x-death") if message.headers else None
    if not deaths:
        return 0
    return sum(int(d.get("count", 0)) for d in deaths if isinstance(d, dict))


async def _on_message(message: AbstractIncomingMessage) -> None:
    """(Nội bộ) On message (async).

    Args:
        message: (AbstractIncomingMessage) Tham số `message`.

    Returns:
        (None) Kết quả trả về."""
    envelope: dict | None = None
    try:
        envelope = json.loads(message.body.decode())
        await dispatch(envelope)
    except AiLayerValidationError:
        logger.exception("[ingest] non-retryable handler error queue=%s", message.routing_key)
        await message.reject(requeue=False)
        return
    except Exception:
        retries = _retry_count(message)
        logger.exception("[ingest] handler failed queue=%s retries=%d", message.routing_key, retries)
        if retries < _MAX_RETRIES:
            await message.nack(requeue=True)
        else:
            await message.reject(requeue=False)
        return
    await message.ack()
    if envelope:
        logger.debug("[ingest] handled key=%s video=%s", envelope.get("routing_key"), envelope.get("video_id") or "-")


async def _consume_queue(queue_name: str) -> None:
    """(Nội bộ) Tiêu thụ queue (async).

    Args:
        queue_name: (str) Tham số `queue_name`.

    Returns:
        (None) Kết quả trả về."""
    channel = await get_channel()
    queue = await channel.get_queue(queue_name)
    await queue.consume(_on_message)
    logger.info("[ingest] consuming queue=%s", queue_name)


async def run_consumer() -> None:
    """Chạy consumer (async).

    Returns:
        (None) Kết quả trả về."""
    await declare_topology()
    await asyncio.gather(*[_consume_queue(name) for name in _QUEUES])
    logger.info("[ingest] consumer running on %d queues", len(_QUEUES))
    await asyncio.Future()
