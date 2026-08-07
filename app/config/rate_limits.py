import app.config.settings as settings


def agent_rate_limit() -> str:
    """Get the configured rate-limit spec for the agent chat endpoint.

    Returns:
        str: The rate-limit spec (e.g. "10/minute") from `settings.AGENT_RATE_LIMIT`.
    """
    return settings.AGENT_RATE_LIMIT


def shorten_rate_limit() -> str:
    """Get the configured rate-limit spec for the URL-shortening endpoint.

    Returns:
        str: The rate-limit spec (e.g. "10/minute") from `settings.SHORTEN_RATE_LIMIT`.
    """
    return settings.SHORTEN_RATE_LIMIT


def qr_rate_limit() -> str:
    """Get the configured rate-limit spec for the QR-code generation endpoint.

    Returns:
        str: The rate-limit spec (e.g. "10/minute") from `settings.QR_RATE_LIMIT`.
    """
    return settings.QR_RATE_LIMIT


def youtube_rate_limit() -> str:
    """Get the configured rate-limit spec for the YouTube-related endpoints.

    Returns:
        str: The rate-limit spec (e.g. "10/minute") from `settings.YOUTUBE_RATE_LIMIT`.
    """
    return settings.YOUTUBE_RATE_LIMIT
