from __future__ import annotations
from aio_pika import ExchangeType
import app.config.settings as settings
from app.config.logger import Logger
from app.ingest.broker.connection import get_channel
from app.ingest.schemas import DLQ_NAME, DLX_NAME, EXCHANGE_NAME, QUEUE_COMMENTS, QUEUE_EMBED, QUEUE_SUMMARIZE, QUEUE_TRANSCRIPT, QUEUE_VIDEO, ROUTING_COMMENTS, ROUTING_EMBED, ROUTING_SUMMARIZE, ROUTING_TRANSCRIPT, ROUTING_VIDEO
logger = Logger.get(__name__)

async def declare_topology() -> None:
    channel = await get_channel()
    exchange_name = settings.RABBITMQ_EXCHANGE or EXCHANGE_NAME
    dlx = await channel.declare_exchange(DLX_NAME, ExchangeType.DIRECT, durable=True)
    dlq = await channel.declare_queue(DLQ_NAME, durable=True)
    await dlq.bind(dlx, routing_key=DLQ_NAME)
    exchange = await channel.declare_exchange(exchange_name, ExchangeType.TOPIC, durable=True)
    bindings = ((QUEUE_VIDEO, ROUTING_VIDEO), (QUEUE_COMMENTS, ROUTING_COMMENTS), (QUEUE_TRANSCRIPT, ROUTING_TRANSCRIPT), (QUEUE_EMBED, ROUTING_EMBED), (QUEUE_SUMMARIZE, ROUTING_SUMMARIZE))
    for queue_name, routing_key in bindings:
        queue = await channel.declare_queue(queue_name, durable=True, arguments={'x-dead-letter-exchange': DLX_NAME, 'x-dead-letter-routing-key': DLQ_NAME})
        await queue.bind(exchange, routing_key=routing_key)
    logger.info('[ingest] topology ready exchange=%s queues=%d', exchange_name, len(bindings))
