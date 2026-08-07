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
    """Return the `admin` section of the config schema.

    Returns:
        The admin schema dict, or `{}` if not defined."""
    return load_schema().get("admin") or {}


def whitelist_keys() -> set[str]:
    """List config keys admins are allowed to read/write.

    Returns:
        The union of all keys across the admin schema's groups plus any
        `standalone_keys`."""
    admin = _admin_schema()
    groups = admin.get("groups") or {}
    keys = {key for group in groups.values() for key in group}
    standalone = admin.get("standalone_keys") or []
    return keys | set(standalone)


def json_keys() -> set[str]:
    """List config keys whose values must be valid JSON strings.

    Returns:
        The `json_keys` set from the admin schema, or `{}` if not defined."""
    return set(_admin_schema().get("json_keys") or [])


async def load_config() -> dict[str, str]:
    """Load the current whitelisted config as a flat key/value mapping.

    Returns:
        The `config` dict from `load_config_bundle()`."""
    bundle = await load_config_bundle()
    return bundle["config"]


async def load_config_bundle() -> dict[str, Any]:
    """Fetch whitelisted config rows from Supabase, including metadata.

    Returns:
        A dict with `config` (key -> value), `updated_at` (key -> ISO
        timestamp string), and `items` (key -> `{"label", "fields"}` for keys
        that define a label or fields). Returns empty collections if Supabase
        is not configured.

    Raises:
        AiLayerError: If the Supabase request fails."""
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
    """Validate and upsert one or more config key/value pairs to Supabase.

    Args:
        updates: Mapping of config key to new string value. Keys must be in
            the admin whitelist; values for JSON-only keys must parse as JSON.

    Returns:
        The list of keys successfully saved (same order as `updates`).

    Raises:
        AiLayerValidationError: If a key isn't whitelisted or a JSON-only
            key's value fails to parse.
        AiLayerError: If Supabase isn't configured or a save request fails."""
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
