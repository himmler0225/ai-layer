"""Ingest worker / RabbitMQ configuration."""

import os


def _env_bool(key: str, default: str = "false") -> bool:
    """(Nội bộ) Env bool `_env_bool`.

    Args:
        key: (str) Tham số `key`.
        default: (str, mặc định 'false') Tham số `default`.

    Returns:
        (bool) Kết quả trả về."""
    return os.getenv(key, default).lower() in {"1", "true", "yes", "on"}


RABBITMQ_URL: str = os.getenv("RABBITMQ_URL", "")
RABBITMQ_EXCHANGE: str = os.getenv("RABBITMQ_EXCHANGE", "knowledge.ingest")
INGEST_ENABLED: bool = _env_bool("INGEST_ENABLED")
INGEST_WORKER_INLINE: bool = _env_bool("INGEST_WORKER_INLINE", "true")
