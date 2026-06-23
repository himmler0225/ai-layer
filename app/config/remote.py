from __future__ import annotations

import json

import httpx

import app.config.settings as settings
import app.services.prompts as prompts
from app.config.logger import Logger

logger = Logger.get(__name__)

_REMOTABLE_STR = frozenset({
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_TOOL_MODEL",
    "DATA_MINER_KEY",
    "AGENT_RATE_LIMIT",
    "QR_RATE_LIMIT",
    "SHORTEN_RATE_LIMIT",
    "YOUTUBE_RATE_LIMIT",
})

_PROMPT_KEYS = frozenset({
    "AGENT_SYSTEM",
    "REVIEW_SUMMARY_SYSTEM",
    "REVIEW_SUMMARY_PROMPT",
})

_REMOTABLE_INT = frozenset({
    "OPENAI_MAX_TOKENS",
    "OPENAI_TOOL_MAX_TOKENS",
    "AGENT_MAX_ITER",
    "AGENT_MAX_RESULT_CHARS",
    "AGENT_MAX_COMMENTS",
    "AGENT_MAX_COMMENT_LEN",
    "AGENT_MAX_LIST_ITEMS",
})


async def load_and_apply() -> None:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        return

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                f"{settings.SUPABASE_URL}/rest/v1/config",
                params={"select": "key,value"},
                headers={
                    "apikey": settings.SUPABASE_SERVICE_KEY,
                    "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                },
            )

            if not response.is_success:
                return

            remote = {
                row["key"]: row["value"]
                for row in response.json()
                if row.get("value") is not None
            }

    except Exception as exc:
        logger.warning("[remote_config] load failed: %s", exc)
        return

    for key in _REMOTABLE_STR:
        if key in remote:
            setattr(settings, key, remote[key])

    for key in _REMOTABLE_INT:
        if key in remote:
            try:
                setattr(settings, key, int(remote[key]))
            except ValueError:
                pass

    for key in _PROMPT_KEYS:
        if key in remote:
            setattr(prompts, key, remote[key])
            if key == "AGENT_SYSTEM":
                settings.AGENT_SYSTEM = remote[key]

    logger.info("[remote_config] applied keys=%d", len(remote))
