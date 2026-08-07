import json
import os
from pathlib import Path
from typing import Any

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "config" / "remote-schema.json"

_INT_FIELD_DEFAULTS: dict[str, int] = {
    "curated_top_n": 300,
}

_BOOL_FIELD_DEFAULTS: dict[str, bool] = {
    "include_review_summary": True,
}

_TYPE_DEFAULTS: dict[str, Any] = {
    "str": "",
    "int": 0,
    "float": 0.0,
    "bool": False,
}


def load_schema() -> dict[str, Any]:
    """Load the remote-config JSON schema from disk.

    Returns:
        dict[str, Any]: The parsed contents of `config/remote-schema.json`.
    """
    with _SCHEMA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _screaming(value: str) -> str:
    """Convert a field name to SCREAMING_CASE for use as a settings attribute suffix.

    Args:
        value: Lowercase (or mixed-case) field name.

    Returns:
        str: The uppercased value.
    """
    return value.upper()


def _default_for(type_name: str) -> Any:
    """Look up the zero-value default for a schema field type.

    Args:
        type_name: One of "str", "int", "float", "bool" (or unknown).

    Returns:
        Any: The default value for that type, or "" if the type is unrecognized.
    """
    return _TYPE_DEFAULTS.get(type_name, "")


def build_settings_defaults(schema: dict[str, Any]) -> dict[str, Any]:
    """Compute the initial `settings` module defaults implied by the remote-config schema.

    Walks each schema key's `bind` block (flat_prefix, provider, service, or
    rate_limit_apis) and any `mirror` rules, producing zero-valued defaults for
    every settings attribute the schema can populate, before any remote or env
    override is applied.

    Args:
        schema: The parsed remote-config schema (see `load_schema`).

    Returns:
        dict[str, Any]: Mapping of settings attribute name to its default value.
    """
    defaults: dict[str, Any] = {}

    for key_schema in schema.get("keys", {}).values():
        bind = key_schema.get("bind") or {}
        bind_type = bind.get("type")

        if bind_type == "flat_prefix" and bind.get("module") == "settings":
            cast = bind.get("cast", "str")
            empty = _default_for("int" if cast == "int" else "str")
            prefix = bind["prefix"]
            for field_name in key_schema.get("fields") or []:
                if field_name in _INT_FIELD_DEFAULTS:
                    defaults[f"{prefix}{_screaming(field_name)}"] = _INT_FIELD_DEFAULTS[field_name]
                else:
                    defaults[f"{prefix}{_screaming(field_name)}"] = empty
            for field_name in key_schema.get("bool_fields") or []:
                defaults[f"{prefix}{_screaming(field_name)}"] = _BOOL_FIELD_DEFAULTS.get(field_name, False)

        elif bind_type == "provider" and bind.get("module") == "settings":
            providers = bind.get("providers") or {}
            string_fields = bind.get("string_fields") or []
            int_fields = bind.get("int_fields") or []
            for prefix in providers.values():
                for field_name in string_fields:
                    defaults[f"{prefix}_{_screaming(field_name)}"] = ""
                for field_name in int_fields:
                    defaults[f"{prefix}_{_screaming(field_name)}"] = 0

        elif bind_type == "service" and bind.get("module") == "settings":
            for service, fields in (bind.get("services") or {}).items():
                prefix = _screaming(service)
                for field_name, type_name in fields.items():
                    defaults[f"{prefix}_{_screaming(field_name)}"] = _default_for(type_name)

        elif bind_type == "rate_limit_apis" and bind.get("module") == "settings":
            for api in bind.get("apis") or []:
                defaults[f"{_screaming(api)}_RATE_LIMIT"] = ""

        for rule in key_schema.get("mirror") or []:
            if rule.get("module") == "settings" and rule.get("attr"):
                defaults[rule["attr"]] = ""

    return defaults


def build_prompt_defaults(schema: dict[str, Any]) -> dict[str, str]:
    """Compute empty-string defaults for every prompt field declared under the PROMPTS key.

    Args:
        schema: The parsed remote-config schema (see `load_schema`).

    Returns:
        dict[str, str]: Mapping of `{GROUP}_{FIELD}` prompt keys to `""`.
    """
    defaults: dict[str, str] = {}
    prompts = schema.get("keys", {}).get("PROMPTS") or {}
    for group, fields in (prompts.get("groups") or {}).items():
        group_key = _screaming(group)
        for field_name in fields:
            defaults[f"{group_key}_{_screaming(field_name)}"] = ""
    return defaults


def env_override(name: str, type_name: str = "str") -> Any | None:
    """Read and type-cast an environment variable override, if present.

    Args:
        name: Environment variable name to look up.
        type_name: Expected type ("str", "bool", "int", or "float") used to
            cast the raw string value.

    Returns:
        Any | None: The cast value, or None if the variable is unset or the
        cast fails.
    """
    raw = os.getenv(name)
    if raw is None:
        return None
    if type_name == "bool":
        return raw.lower() in {"1", "true", "yes", "on"}
    if type_name == "int":
        try:
            return int(raw)
        except ValueError:
            return None
    if type_name == "float":
        try:
            return float(raw)
        except ValueError:
            return None
    return raw


def apply_env_fallbacks(
    remote: dict[str, Any],
    schema: dict[str, Any],
) -> dict[str, Any]:
    """Fill in service settings (and the data-miner service token) from environment
    variables wherever the remote config left them empty.

    Args:
        remote: The in-progress remote settings dict to patch in place.
        schema: The parsed remote-config schema, used to enumerate service fields.

    Returns:
        dict[str, Any]: The same `remote` dict, mutated with env fallback values.
    """
    services = (schema.get("keys", {}).get("SERVICES") or {}).get("bind", {}).get("services") or {}
    for service, fields in services.items():
        prefix = _screaming(service)
        for field_name, type_name in fields.items():
            attr = f"{prefix}_{_screaming(field_name)}"
            if remote.get(attr) in (None, "", 0, 0.0, False):
                env_val = env_override(attr, type_name)
                if env_val is not None:
                    remote[attr] = env_val
    token = env_override("DATA_MINER_SERVICE_TOKEN")
    if token and not remote.get("DATA_MINER_SERVICE_TOKEN"):
        remote["DATA_MINER_SERVICE_TOKEN"] = token
    return remote
