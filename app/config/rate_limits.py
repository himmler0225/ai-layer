"""Callable rate-limit resolvers — read settings at request time (after remote config)."""

from __future__ import annotations

import app.config.settings as _s


def agent_rate_limit() -> str:
    return _s.AGENT_RATE_LIMIT


def shorten_rate_limit() -> str:
    return _s.SHORTEN_RATE_LIMIT


def qr_rate_limit() -> str:
    return _s.QR_RATE_LIMIT


def youtube_rate_limit() -> str:
    return _s.YOUTUBE_RATE_LIMIT
