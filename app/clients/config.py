"""Data-miner HTTP client configuration."""

import app.config.settings as settings
from app.config.constants import (
    DATA_MINER_MAX_CONN,
    DATA_MINER_MAX_KEEPALIVE,
    HTTP_MAX_ATTEMPTS,
    HTTP_RETRY_STATUSES,
)


def base_url() -> str:
    return settings.DATA_MINER_URL


def api_key() -> str:
    return settings.DATA_MINER_KEY


def service_token() -> str:
    return settings.DATA_MINER_SERVICE_TOKEN


def timeout() -> float:
    return settings.DATA_MINER_TIMEOUT


def movie_default_provider() -> str:
    return settings.MOVIE_DEFAULT_PROVIDER
