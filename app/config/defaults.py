from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "config" / "remote-schema.json"

_INT_FIELD_DEFAULTS: dict[str, int] = {
    "curated_top_n": 300,
}

_TYPE_DEFAULTS: dict[str, Any] = {
    "str": "",
    "int": 0,
    "float": 0.0,
    "bool": False,
}


def load_schema() -> dict[str, Any]:
    with _SCHEMA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _screaming(value: str) -> str:
    return value.upper()


def _default_for(type_name: str) -> Any:
    return _TYPE_DEFAULTS.get(type_name, "")


def build_settings_defaults(schema: dict[str, Any]) -> dict[str, Any]:
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
                    defaults[f"{prefix}{_screaming(field_name)}"] = _INT_FIELD_DEFAULTS[
                        field_name
                    ]
                else:
                    defaults[f"{prefix}{_screaming(field_name)}"] = empty

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
    defaults: dict[str, str] = {}
    prompts = schema.get("keys", {}).get("PROMPTS") or {}
    for group, fields in (prompts.get("groups") or {}).items():
        group_key = _screaming(group)
        for field_name in fields:
            defaults[f"{group_key}_{_screaming(field_name)}"] = ""
    return defaults


def env_override(name: str, type_name: str = "str") -> Optional[Any]:
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
