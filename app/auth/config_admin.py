import json
from datetime import datetime, UTC
from typing import Any

import httpx

from app.config.constants import REMOTE_CONFIG_TIMEOUT
from app.config.defaults import load_schema
from app.config.headers import get_supabase_rest_headers
from app.config.settings import SUPABASE_SERVICE_KEY, SUPABASE_URL
from app.exceptions import AiLayerError, AiLayerValidationError


def _admin_schema() -> dict[str, Any]:
    """(Nội bộ) Admin schema `_admin_schema`.

    Returns:
        (dict[str, Any]) Kết quả trả về."""
    return load_schema().get("admin") or {}


def whitelist_keys() -> set[str]:
    """Whitelist keys.

    Returns:
        (set[str]) Kết quả trả về."""
    admin = _admin_schema()
    groups = admin.get("groups") or {}
    keys = {key for group in groups.values() for key in group}
    standalone = admin.get("standalone_keys") or []
    return keys | set(standalone)


def json_keys() -> set[str]:
    """Json keys.

    Returns:
        (set[str]) Kết quả trả về."""
    return set(_admin_schema().get("json_keys") or [])


async def load_config() -> dict[str, str]:
    """Tải config (async).

    Returns:
        (dict[str, str]) Kết quả trả về."""
    bundle = await load_config_bundle()
    return bundle["config"]


async def load_config_bundle() -> dict[str, Any]:
    """Tải config bundle (async).

    Returns:
        (dict[str, Any]) Kết quả trả về."""
    allowed = whitelist_keys()
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return {"config": {}, "updated_at": {}, "items": {}}
    async with httpx.AsyncClient(timeout=REMOTE_CONFIG_TIMEOUT) as client:
        r = await client.get(
            f"{SUPABASE_URL}/rest/v1/config",
            params={"select": "key,value,updated_at,label,fields"},
            headers=get_supabase_rest_headers(SUPABASE_SERVICE_KEY),
        )
    if not r.is_success:
        raise AiLayerError("Failed to load config")
    config: dict[str, str] = {}
    updated_at: dict[str, str] = {}
    items: dict[str, dict[str, Any]] = {}
    for row in r.json():
        key = row.get("key")
        value = row.get("value")
        if key in allowed and value is not None:
            config[key] = value
            if row.get("updated_at"):
                updated_at[key] = str(row["updated_at"])
            label = row.get("label")
            fields = row.get("fields")
            if label is not None or fields is not None:
                items[key] = {
                    "label": label,
                    "fields": fields,
                }
    return {"config": config, "updated_at": updated_at, "items": items}


async def patch_config(updates: dict[str, str]) -> list[str]:
    """Patch config (async).

    Args:
        updates: (dict[str, str]) Tham số `updates`.

    Returns:
        (list[str]) Kết quả trả về."""
    allowed = whitelist_keys()
    json_only = json_keys()
    saved: list[str] = []
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise AiLayerError("Supabase service key is not configured")

    for key, value in updates.items():
        if key not in allowed:
            raise AiLayerValidationError(f"Key not allowed: {key}")
        if key in json_only:
            try:
                json.loads(value)
            except json.JSONDecodeError as exc:
                raise AiLayerValidationError(f"Invalid JSON for {key}") from exc

    now = datetime.now(UTC).isoformat()
    async with httpx.AsyncClient(timeout=REMOTE_CONFIG_TIMEOUT) as client:
        for key, value in updates.items():
            r = await client.post(
                f"{SUPABASE_URL}/rest/v1/config",
                headers={
                    **get_supabase_rest_headers(SUPABASE_SERVICE_KEY),
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates,return=minimal",
                },
                json={"key": key, "value": value, "updated_at": now},
            )
            if not r.is_success:
                raise AiLayerError(f"Failed to save config key: {key}")
            saved.append(key)
    return saved
