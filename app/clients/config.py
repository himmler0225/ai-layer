"""Data-miner HTTP client configuration."""

import app.config.settings as settings
from app.config.constants import (
    DATA_MINER_MAX_CONN,
    DATA_MINER_MAX_KEEPALIVE,
    HTTP_MAX_ATTEMPTS,
    HTTP_RETRY_STATUSES,
)


def base_url() -> str:
    """Return the configured data-miner service base URL.

    Returns:
        The `DATA_MINER_URL` setting value."""
    return settings.DATA_MINER_URL


def api_key() -> str:
    """Return the API key used to authenticate with the data-miner service.

    Returns:
        The `DATA_MINER_KEY` setting value."""
    return settings.DATA_MINER_KEY


def service_token() -> str:
    """Return the service token used to authenticate with the data-miner service.

    Returns:
        The `DATA_MINER_SERVICE_TOKEN` setting value."""
    return settings.DATA_MINER_SERVICE_TOKEN


def timeout() -> float:
    """Return the HTTP timeout (seconds) for data-miner requests.

    Returns:
        The `DATA_MINER_TIMEOUT` setting value."""
    return settings.DATA_MINER_TIMEOUT


def movie_default_provider() -> str:
    """Return the default movie data provider to use when none is specified.

    Returns:
        The `MOVIE_DEFAULT_PROVIDER` setting value."""
    return settings.MOVIE_DEFAULT_PROVIDER
