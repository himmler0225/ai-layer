"""Load Supabase bảng `config` → settings + prompts."""

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
    "DEEP_SEEK_API_KEY",
    "DEEP_SEEK_MODEL",
    "DEEP_SEEK_TOOL_MODEL",
    "DATA_MINER_KEY",
    "AGENT_RATE_LIMIT",
    "QR_RATE_LIMIT",
    "SHORTEN_RATE_LIMIT",
    "YOUTUBE_RATE_LIMIT",
})

_PROMPT_KEYS = frozenset({
    "AGENT_SYSTEM",
    "AGENT_SYNTH_SYSTEM",
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

_REQUIRED_KEYS = frozenset({
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "DEEP_SEEK_API_KEY",
    "DEEP_SEEK_MODEL",
    "OPENAI_MAX_TOKENS",
    "AGENT_MAX_ITER",
    "AGENT_SYSTEM",
    "REVIEW_SUMMARY_SYSTEM",
    "REVIEW_SUMMARY_PROMPT",
})


def _value_for_key(key: str) -> str | int:
    if key in _PROMPT_KEYS:
        return getattr(prompts, key, "")
    return getattr(settings, key, "")


def validate_config() -> None:
    """Sau load_and_apply — báo lỗi nếu thiếu key bắt buộc."""
    missing: list[str] = []
    for key in _REQUIRED_KEYS:
        val = _value_for_key(key)
        if isinstance(val, int):
            if val <= 0 and key == "AGENT_MAX_ITER":
                missing.append(key)
            elif val <= 0 and key == "OPENAI_MAX_TOKENS":
                missing.append(key)
        elif not str(val).strip():
            missing.append(key)
    if missing:
        raise RuntimeError(
            "Thiếu config trên Supabase (bảng config): "
            + ", ".join(sorted(missing))
        )


async def load_and_apply() -> None:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        logger.warning("[remote_config] SUPABASE_URL/SERVICE_KEY trống — bỏ qua load")
        validate_config()
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
                logger.warning("[remote_config] fetch failed status=%s", response.status_code)
                validate_config()
                return

            remote = {
                row["key"]: row["value"]
                for row in response.json()
                if row.get("value") is not None
            }

    except Exception as exc:
        logger.warning("[remote_config] load failed: %s", exc)
        validate_config()
        return

    for key in _REMOTABLE_STR:
        if key in remote:
            setattr(settings, key, remote[key])

    for key in _REMOTABLE_INT:
        if key in remote:
            try:
                setattr(settings, key, int(remote[key]))
            except ValueError:
                logger.warning("[remote_config] invalid int key=%s", key)

    for key in _PROMPT_KEYS:
        if key in remote:
            setattr(prompts, key, remote[key])
            if key == "AGENT_SYSTEM":
                settings.AGENT_SYSTEM = remote[key]

    logger.info("[remote_config] applied keys=%d", len(remote))
    validate_config()
