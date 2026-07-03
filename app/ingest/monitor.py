import aio_pika
from app.ingest.config import INGEST_ENABLED, RABBITMQ_EXCHANGE, RABBITMQ_URL
from app.ingest.schemas import DLQ_NAME, EXCHANGE_NAME, QUEUE_COMMENTS, QUEUE_EMBED, QUEUE_TRANSCRIPT, QUEUE_VIDEO

_INGEST_QUEUES = (QUEUE_VIDEO, QUEUE_COMMENTS, QUEUE_TRANSCRIPT, QUEUE_EMBED)


async def _queue_info(channel, name: str) -> dict:
    """(Nội bộ) Queue info (async).

    Args:
        channel: (Any) Tham số `channel`.
        name: (str) Tham số `name`.

    Returns:
        (dict) Kết quả trả về."""
    queue = await channel.declare_queue(name, passive=True)
    result = queue.declaration_result
    return {"messages": result.message_count, "consumers": result.consumer_count}


async def get_ingest_queue_stats() -> dict:
    """Lấy ingest queue stats (async).

    Returns:
        (dict) Kết quả trả về."""
    if not RABBITMQ_URL:
        return {"enabled": False, "ingest_enabled": INGEST_ENABLED, "reason": "RABBITMQ_URL chưa cấu hình"}
    conn = await aio_pika.connect_robust(RABBITMQ_URL)
    try:
        channel = await conn.channel()
        queues = {}
        for name in _INGEST_QUEUES:
            try:
                queues[name] = await _queue_info(channel, name)
            except Exception as exc:
                queues[name] = {"messages": None, "consumers": None, "error": str(exc)}
        try:
            dlq = await _queue_info(channel, DLQ_NAME)
        except Exception as exc:
            dlq = {"messages": None, "consumers": None, "error": str(exc)}
        total_pending = sum(q.get("messages") or 0 for q in queues.values() if isinstance(q.get("messages"), int))
        return {
            "enabled": True,
            "ingest_enabled": INGEST_ENABLED,
            "exchange": RABBITMQ_EXCHANGE or EXCHANGE_NAME,
            "queues": queues,
            "dlq": dlq,
            "total_pending": total_pending,
            "dlq_messages": dlq.get("messages"),
            "management_ui_hint": "http://localhost:15672 (user: ingest)",
        }
    finally:
        await conn.close()
