from __future__ import annotations

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
})

_PROMPT_KEY = "AGENT_SYSTEM"

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

    if _PROMPT_KEY in remote:
        prompts.AGENT_SYSTEM = remote[_PROMPT_KEY]
        settings.AGENT_SYSTEM = remote[_PROMPT_KEY]

    logger.info("[remote_config] applied keys=%d", len(remote))
