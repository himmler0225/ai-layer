"""Rate limit động — đọc settings lúc request (sau remote config)."""

from __future__ import annotations

import app.config.settings as settings


def agent_rate_limit() -> str:
    """Giới hạn endpoint agent."""
    return settings.AGENT_RATE_LIMIT


def shorten_rate_limit() -> str:
    """Giới hạn rút gọn URL."""
    return settings.SHORTEN_RATE_LIMIT


def qr_rate_limit() -> str:
    """Giới hạn tạo QR."""
    return settings.QR_RATE_LIMIT


def youtube_rate_limit() -> str:
    """Giới hạn API YouTube AI."""
    return settings.YOUTUBE_RATE_LIMIT
