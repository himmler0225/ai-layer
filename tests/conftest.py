from __future__ import annotations

from typing import Any

from app.config.defaults import load_schema
from app.config.loader import provider_settings_prefix

_PROVIDER_FIELDS = {
    "api_key": "API_KEY",
    "base_url": "BASE_URL",
    "model": "MODEL",
    "max_tokens": "MAX_TOKENS",
    "tool_model": "TOOL_MODEL",
    "tool_max_tokens": "TOOL_MAX_TOKENS",
}


def set_provider_remote(
    settings: Any,
    provider_id: str,
    schema: dict | None = None,
    **fields: Any,
) -> str:
    """Ghi settings._REMOTE cho một provider; trả về settings prefix."""
    schema = schema or load_schema()
    prefix = provider_settings_prefix(provider_id, schema)
    defaults = {
        "api_key": "test-key",
        "base_url": "https://api.example.com/v1",
        "model": "model-main",
        "max_tokens": 4096,
        "tool_model": "model-tool",
        "tool_max_tokens": 3072,
    }
    merged = {**defaults, **fields}
    for name, val in merged.items():
        attr = _PROVIDER_FIELDS.get(name, name.upper())
        settings._REMOTE[f"{prefix}_{attr}"] = val
    return prefix
