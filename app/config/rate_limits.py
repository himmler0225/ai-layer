from __future__ import annotations
import app.config.settings as settings

def agent_rate_limit() -> str:
    """Agent rate limit.

    Returns:
        (str) Kết quả trả về."""
    return settings.AGENT_RATE_LIMIT

def shorten_rate_limit() -> str:
    """Shorten rate limit.

    Returns:
        (str) Kết quả trả về."""
    return settings.SHORTEN_RATE_LIMIT

def qr_rate_limit() -> str:
    """Qr rate limit.

    Returns:
        (str) Kết quả trả về."""
    return settings.QR_RATE_LIMIT

def youtube_rate_limit() -> str:
    """Youtube rate limit.

    Returns:
        (str) Kết quả trả về."""
    return settings.YOUTUBE_RATE_LIMIT
