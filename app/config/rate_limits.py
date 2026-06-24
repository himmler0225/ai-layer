"""Rate limit động — đọc settings lúc request (sau remote config)."""

from __future__ import annotations

import app.config.settings as _s


def agent_rate_limit() -> str:
    """Giới hạn endpoint agent."""
    return _s.AGENT_RATE_LIMIT


def shorten_rate_limit() -> str:
    """Giới hạn rút gọn URL."""
    return _s.SHORTEN_RATE_LIMIT


def qr_rate_limit() -> str:
    """Giới hạn tạo QR."""
    return _s.QR_RATE_LIMIT


def youtube_rate_limit() -> str:
    """Giới hạn API YouTube AI."""
    return _s.YOUTUBE_RATE_LIMIT
