from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any, Callable

import app.config.settings as settings
import app.services.prompts as prompts
from app.config.defaults import (
    apply_env_fallbacks,
    build_prompt_defaults,
    build_settings_defaults,
    load_schema as _load_schema,
)
from app.config.logger import Logger

logger = Logger.get(__name__)


@dataclass
class AgentConfig:
    max_iter: int = 0
    max_comments: int = 0
    max_comment_len: int = 0
    max_list_items: int = 0
    max_result_chars: int = 0


@dataclass
class RuntimeConfig:
    agent: AgentConfig = field(default_factory=AgentConfig)
    models: dict[str, Any] = field(default_factory=dict)
    prompts: dict[str, Any] = field(default_factory=dict)
    services: dict[str, Any] = field(default_factory=dict)
    rate_limit: dict[str, Any] = field(default_factory=dict)


runtime = RuntimeConfig()


def load_schema() -> dict[str, Any]:
    return _load_schema()


def parse_remote(raw: dict[str, str]) -> dict[str, Any]:
    import json

    parsed: dict[str, Any] = {}
    for key, value in raw.items():
        if value is None:
            continue
        try:
            parsed[key] = json.loads(value)
        except json.JSONDecodeError:
            parsed[key] = value
    return parsed


def _screaming(value: str) -> str:
    return value.upper()


def _set_module_value(module: str, attr: str, value: Any) -> None:
    if module == "settings":
        settings.set_remote(attr, value)
    elif module == "prompts":
        prompts.set_prompt(attr, str(value))
    else:
        raise ValueError(f"unknown module: {module}")


def _apply_flat_prefix(data: dict, bind: dict, key_schema: dict) -> None:
    prefix = bind["prefix"]
    cast = bind.get("cast")
    field_names = key_schema.get("fields") or list(data.keys())
    for field_name in field_names:
        if field_name not in data or data[field_name] is None:
            continue
        try:
            val = int(data[field_name]) if cast == "int" else data[field_name]
            _set_module_value(bind["module"], f"{prefix}{_screaming(field_name)}", val)
        except (TypeError, ValueError):
            logger.warning("[remote_config] invalid int %s.%s", prefix, field_name)


def _apply_group_field(data: dict, bind: dict) -> None:
    for group, group_data in data.items():
        if not isinstance(group_data, dict):
            continue
        group_key = _screaming(group)
        for field_name, value in group_data.items():
            if value is None:
                continue
            _set_module_value(
                bind["module"],
                f"{group_key}_{_screaming(field_name)}",
                value,
            )


def _apply_provider(data: dict, bind: dict) -> None:
    providers = bind.get("providers") or {}
    int_fields = set(bind.get("int_fields") or [])
    for provider, provider_data in data.items():
        if not isinstance(provider_data, dict):
            continue
        prefix = providers.get(provider, _screaming(provider))
        for field_name, value in provider_data.items():
            if value is None:
                continue
            attr = f"{prefix}_{_screaming(field_name)}"
            try:
                val = int(value) if field_name in int_fields else value
                _set_module_value(bind["module"], attr, val)
            except (TypeError, ValueError):
                pass


def _apply_service(data: dict, bind: dict) -> None:
    service_types = bind.get("services") or {}
    for service, service_data in data.items():
        if not isinstance(service_data, dict):
            continue
        prefix = _screaming(service)
        types = service_types.get(service) or {}
        for field_name, value in service_data.items():
            if value is None:
                continue
            attr = f"{prefix}_{_screaming(field_name)}"
            type_name = types.get(field_name, "str")
            if type_name == "bool" and isinstance(value, str):
                value = value.lower() in {"1", "true", "yes", "on"}
            elif type_name == "int":
                value = int(value)
            elif type_name == "float":
                value = float(value)
            _set_module_value(bind["module"], attr, value)


def _apply_rate_limit_apis(data: dict, bind: dict) -> None:
    apis = bind.get("apis") or list((data.get("apis") or {}).keys())
    source = data.get("apis") or data
    for name in apis:
        val = source.get(name)
        if val:
            _set_module_value(bind["module"], f"{_screaming(name)}_RATE_LIMIT", val)


def _apply_mirror(data: dict, mirror: list[dict]) -> None:
    for rule in mirror:
        group_data = data.get(rule["group"]) or {}
        value = group_data.get(rule["field"]) if isinstance(group_data, dict) else None
        if value is None:
            continue
        _set_module_value(rule["module"], rule["attr"], value)


def _store_runtime(key: str, data: Any, key_schema: dict) -> None:
    store = key_schema.get("store")
    if not store or data is None:
        return
    if store == "agent" and isinstance(data, dict):
        known = {f.name for f in fields(AgentConfig)}
        runtime.agent = AgentConfig(
            **{
                k: int(data[k])
                for k in (key_schema.get("fields") or [])
                if k in known and k in data and data[k] is not None
            }
        )
    elif store in {"models", "prompts", "services", "rate_limit"} and isinstance(
        data, dict
    ):
        setattr(runtime, store, data)


_BINDERS: dict[str, Callable[..., None]] = {
    "group_field": _apply_group_field,
    "provider": _apply_provider,
    "service": _apply_service,
    "rate_limit_apis": _apply_rate_limit_apis,
}


def _prompt_keys(schema: dict[str, Any]) -> frozenset[str]:
    prompt_cfg = schema.get("keys", {}).get("PROMPTS") or {}
    keys: set[str] = set()
    for group, field_list in (prompt_cfg.get("groups") or {}).items():
        group_key = _screaming(group)
        for field_name in field_list:
            keys.add(f"{group_key}_{_screaming(field_name)}")
    return frozenset(keys)


def apply_schema(parsed: dict[str, Any], schema: dict[str, Any]) -> None:
    settings.ensure_remote_defaults()
    prompts.init_defaults(build_prompt_defaults(schema))

    for key, key_schema in schema.get("keys", {}).items():
        data = parsed.get(key)
        if data is None:
            continue
        bind = key_schema.get("bind") or {}
        bind_type = bind.get("type")
        if bind_type == "flat_prefix" and isinstance(data, dict):
            _apply_flat_prefix(data, bind, key_schema)
        elif bind_type in _BINDERS and isinstance(data, dict):
            _BINDERS[bind_type](data, bind)
        mirror = key_schema.get("mirror")
        if mirror and isinstance(data, dict):
            _apply_mirror(data, mirror)
        _store_runtime(key, data, key_schema)

    apply_env_fallbacks(settings._REMOTE, schema)


def value_for_required(key: str, schema: dict[str, Any]) -> str | int:
    if key in _prompt_keys(schema) and key != "AGENT_SYSTEM":
        return getattr(prompts, key, "")
    return getattr(settings, key, "")


def validate_required(schema: dict[str, Any]) -> None:
    missing: list[str] = []
    for key in schema.get("required") or []:
        val = value_for_required(key, schema)
        if isinstance(val, int):
            if val <= 0 and key in {"AGENT_MAX_ITER", "OPENAI_MAX_TOKENS"}:
                missing.append(key)
        elif not str(val).strip():
            missing.append(key)
    if missing:
        raise RuntimeError(
            "Missing Supabase config keys: " + ", ".join(sorted(missing))
        )
