import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractRobustConnection
from app.exceptions import AiLayerConfigError
from app.ingest.config import RABBITMQ_EXCHANGE, RABBITMQ_URL
from app.ingest.schemas import EXCHANGE_NAME

_connection: AbstractRobustConnection | None = None
_channel: AbstractChannel | None = None
_exchange: aio_pika.abc.AbstractExchange | None = None


async def get_connection() -> AbstractRobustConnection:
    """Lấy connection (async).

    Returns:
        (AbstractRobustConnection) Kết quả trả về."""
    global _connection
    if _connection is None or _connection.is_closed:
        if not RABBITMQ_URL:
            raise AiLayerConfigError("RABBITMQ_URL is not configured")
        _connection = await aio_pika.connect_robust(RABBITMQ_URL)
    return _connection


async def get_channel() -> AbstractChannel:
    """Lấy channel (async).

    Returns:
        (AbstractChannel) Kết quả trả về."""
    global _channel
    conn = await get_connection()
    if _channel is None or _channel.is_closed:
        _channel = await conn.channel()
        await _channel.set_qos(prefetch_count=8)
    return _channel


async def get_exchange() -> aio_pika.abc.AbstractExchange:
    """Lấy exchange (async).

    Returns:
        (aio_pika.abc.AbstractExchange) Kết quả trả về."""
    global _exchange
    if _exchange is None:
        channel = await get_channel()
        _exchange = await channel.declare_exchange(
            RABBITMQ_EXCHANGE or EXCHANGE_NAME, ExchangeType.TOPIC, durable=True
        )
    return _exchange


async def close_broker() -> None:
    """Đóng broker (async).

    Returns:
        (None) Kết quả trả về."""
    global _connection, _channel, _exchange
    if _channel and (not _channel.is_closed):
        await _channel.close()
    if _connection and (not _connection.is_closed):
        await _connection.close()
    _channel = None
    _connection = None
    _exchange = None
