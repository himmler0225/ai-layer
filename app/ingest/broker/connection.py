from __future__ import annotations

from typing import Optional

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractRobustConnection

import app.config.settings as _cfg
from app.ingest.schemas import EXCHANGE_NAME

_connection: Optional[AbstractRobustConnection] = None
_channel: Optional[AbstractChannel] = None
_exchange: Optional[aio_pika.abc.AbstractExchange] = None


async def get_connection() -> AbstractRobustConnection:
    """Mở kết nối robust tới RabbitMQ (tái dùng singleton)."""
    global _connection
    if _connection is None or _connection.is_closed:
        if not _cfg.RABBITMQ_URL:
            raise RuntimeError("RABBITMQ_URL is not configured")
        _connection = await aio_pika.connect_robust(_cfg.RABBITMQ_URL)
    return _connection


async def get_channel() -> AbstractChannel:
    """Lấy channel RabbitMQ (prefetch 8 job/lần)."""
    global _channel
    conn = await get_connection()
    if _channel is None or _channel.is_closed:
        _channel = await conn.channel()
        await _channel.set_qos(prefetch_count=8)
    return _channel


async def get_exchange() -> aio_pika.abc.AbstractExchange:
    """Khai báo exchange topic dùng chung producer/consumer."""
    global _exchange
    if _exchange is None:
        channel = await get_channel()
        _exchange = await channel.declare_exchange(
            _cfg.RABBITMQ_EXCHANGE or EXCHANGE_NAME,
            ExchangeType.TOPIC,
            durable=True,
        )
    return _exchange


async def close_broker() -> None:
    """Đóng channel và connection khi shutdown."""
    global _connection, _channel, _exchange
    if _channel and not _channel.is_closed:
        await _channel.close()
    if _connection and not _connection.is_closed:
        await _connection.close()
    _channel = None
    _connection = None
    _exchange = None
