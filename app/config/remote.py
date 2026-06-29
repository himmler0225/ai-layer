from __future__ import annotations

import httpx

import app.config.settings as settings
from app.config.constants import REMOTE_CONFIG_TIMEOUT
from app.config.headers import get_supabase_rest_headers
from app.config.loader import apply_schema, load_schema, parse_remote, validate_required
from app.config.logger import Logger

logger = Logger.get(__name__)


async def load_and_apply() -> None:
    """Tải and apply (async).

    Returns:
        (None) Kết quả trả về."""
    schema = load_schema()

    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        validate_required(schema)
        return

    try:
        async with httpx.AsyncClient(timeout=REMOTE_CONFIG_TIMEOUT) as client:
            response = await client.get(
                f"{settings.SUPABASE_URL}/rest/v1/config",
                params={"select": "key,value"},
                headers=get_supabase_rest_headers(settings.SUPABASE_SERVICE_KEY),
            )
            if not response.is_success:
                validate_required(schema)
                return
            remote = {
                row["key"]: row["value"]
                for row in response.json()
                if row.get("value")
            }
    except Exception:
        validate_required(schema)
        return

    apply_schema(parse_remote(remote), schema)
    logger.info("[remote_config] applied keys=%d", len(remote))
    validate_required(schema)
