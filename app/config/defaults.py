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
    """Tải schema.

    Returns:
        (dict[str, Any]) Kết quả trả về."""
    with _SCHEMA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _screaming(value: str) -> str:
    """(Nội bộ) Screaming `_screaming`.

    Args:
        value: (str) Tham số `value`.

    Returns:
        (str) Kết quả trả về."""
    return value.upper()


def _default_for(type_name: str) -> Any:
    """(Nội bộ) Default for.

    Args:
        type_name: (str) Tham số `type_name`.

    Returns:
        (Any) Kết quả trả về."""
    return _TYPE_DEFAULTS.get(type_name, "")


def build_settings_defaults(schema: dict[str, Any]) -> dict[str, Any]:
    """Xây dựng settings defaults.

    Args:
        schema: (dict[str, Any]) Tham số `schema`.

    Returns:
        (dict[str, Any]) Kết quả trả về."""
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
    """Xây dựng prompt defaults.

    Args:
        schema: (dict[str, Any]) Tham số `schema`.

    Returns:
        (dict[str, str]) Kết quả trả về."""
    defaults: dict[str, str] = {}
    prompts = schema.get("keys", {}).get("PROMPTS") or {}
    for group, fields in (prompts.get("groups") or {}).items():
        group_key = _screaming(group)
        for field_name in fields:
            defaults[f"{group_key}_{_screaming(field_name)}"] = ""
    return defaults


def env_override(name: str, type_name: str = "str") -> Any | None:
    """Env override.

    Args:
        name: (str) Tham số `name`.
        type_name: (str, mặc định 'str') Tham số `type_name`.

    Returns:
        (Optional[Any]) Kết quả trả về."""
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
    """Áp dụng env fallbacks.

    Args:
        remote: (dict[str, Any]) Tham số `remote`.
        schema: (dict[str, Any]) Tham số `schema`.

    Returns:
        (dict[str, Any]) Kết quả trả về."""
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
