from __future__ import annotations
import app.config.settings as settings

def agent_rate_limit() -> str:
    return settings.AGENT_RATE_LIMIT

def shorten_rate_limit() -> str:
    return settings.SHORTEN_RATE_LIMIT

def qr_rate_limit() -> str:
    return settings.QR_RATE_LIMIT

def youtube_rate_limit() -> str:
    return settings.YOUTUBE_RATE_LIMIT
