"""Client OpenAI async dùng chung."""

from typing import Optional
from openai import AsyncOpenAI

import app.config.settings as _cfg

_openai_client: Optional[AsyncOpenAI] = None


def get_openai_client() -> AsyncOpenAI:
    """Lấy hoặc tạo singleton AsyncOpenAI."""
    global _openai_client

    if not _cfg.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    if not _cfg.OPENAI_MODEL:
        raise RuntimeError("OPENAI_MODEL is not configured")

    if _openai_client is None:
        _openai_client = AsyncOpenAI(
            api_key=_cfg.OPENAI_API_KEY
        )

    return _openai_client