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
    """Write a provider's config directly into settings._REMOTE for tests.

    Merges the given field overrides on top of sensible test defaults
    (api_key, base_url, model, max_tokens, tool_model, tool_max_tokens) and
    stores them under the provider's settings key prefix.

    Args:
        settings: The settings module (or stand-in) whose _REMOTE dict is written to.
        provider_id: id of the provider to configure.
        schema: Config schema used to resolve the provider's settings prefix;
            loaded via load_schema() if not given.
        fields: Overrides for the default test values.

    Returns:
        The settings key prefix used for this provider."""
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
