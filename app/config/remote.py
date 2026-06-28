"""Load Supabase bảng `config` → settings + prompts."""

from __future__ import annotations

import httpx

import app.config.settings as settings
from app.config.constants import REMOTE_CONFIG_TIMEOUT
from app.config.headers import get_supabase_rest_headers
from app.config.loader import (apply_schema, load_schema, parse_remote,
                               validate_required)
from app.config.logger import Logger

logger = Logger.get(__name__)
_schema = load_schema()


async def _fetch_remote() -> dict[str, str] | None:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        return None
    async with httpx.AsyncClient(timeout=REMOTE_CONFIG_TIMEOUT) as client:
        response = await client.get(
            f"{settings.SUPABASE_URL}/rest/v1/config",
            params={"select": "key,value"},
            headers=get_supabase_rest_headers(settings.SUPABASE_SERVICE_KEY),
        )
        if not response.is_success:
            logger.warning(
                "[remote_config] fetch failed status=%s", response.status_code
            )
            return None
        return {
            row["key"]: row["value"]
            for row in response.json()
            if row.get("value") is not None
        }


async def load_and_apply() -> None:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        logger.warning("[remote_config] SUPABASE_URL/SERVICE_KEY trống — bỏ qua load")
        validate_required(_schema)
        return

    try:
        remote = await _fetch_remote()
    except Exception as exc:
        logger.warning("[remote_config] load failed: %s", exc)
        validate_required(_schema)
        return

    if not remote:
        validate_required(_schema)
        return

    apply_schema(parse_remote(remote), _schema)
    logger.info("[remote_config] applied keys=%d", len(remote))
    validate_required(_schema)
