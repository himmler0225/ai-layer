from __future__ import annotations

import asyncio
import json

from aio_pika.abc import AbstractIncomingMessage

from app.config.logger import Logger
from app.ingest.broker import declare_topology, get_channel
from app.ingest.handlers.router import dispatch
from app.ingest.schemas import (
    QUEUE_COMMENTS,
    QUEUE_EMBED,
    QUEUE_TRANSCRIPT,
    QUEUE_VIDEO,
)

logger = Logger.get(__name__)
_QUEUES = (QUEUE_VIDEO, QUEUE_COMMENTS, QUEUE_TRANSCRIPT, QUEUE_EMBED)


async def _on_message(message: AbstractIncomingMessage) -> None:
    """Đọc envelope JSON và gọi handler tương ứng."""
    async with message.process(requeue=False):
        envelope = json.loads(message.body.decode())
        await dispatch(envelope)
        logger.debug(
            "[ingest] handled key=%s video=%s",
            envelope.get("routing_key"),
            envelope.get("video_id") or "-",
        )


async def _consume_queue(queue_name: str) -> None:
    """Lắng nghe một queue RabbitMQ."""
    channel = await get_channel()
    queue = await channel.get_queue(queue_name)
    await queue.consume(_on_message)
    logger.info("[ingest] consuming queue=%s", queue_name)


async def run_consumer() -> None:
    """Bật worker lắng nghe cả 4 queue ingest."""
    await declare_topology()
    await asyncio.gather(*[_consume_queue(name) for name in _QUEUES])
    logger.info("[ingest] consumer running on %d queues", len(_QUEUES))
    await asyncio.Future()
