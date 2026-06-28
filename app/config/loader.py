"""Schema-driven remote config loader — ai-layer (no proxy; proxy lives in data-miner)."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Callable

import app.config.settings as settings
import app.services.prompts as prompts
from app.config.logger import Logger

logger = Logger.get(__name__)

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "config" / "remote-schema.json"

_PROMPT_MAP: dict[tuple[str, str], tuple[str, str]] = {
    ("agent", "system"): ("AGENT_SYSTEM", "settings"),
    ("agent", "synth_system"): ("AGENT_SYNTH_SYSTEM", "prompts"),
    ("review_summary", "system"): ("REVIEW_SUMMARY_SYSTEM", "prompts"),
    ("review_summary", "prompt"): ("REVIEW_SUMMARY_PROMPT", "prompts"),
    ("aspect_group", "system"): ("ASPECT_GROUP_SYSTEM", "prompts"),
    ("aspect_group", "prompt"): ("ASPECT_GROUP_PROMPT", "prompts"),
    ("aspect_summary", "system"): ("ASPECT_SUMMARY_SYSTEM", "prompts"),
    ("aspect_summary", "prompt"): ("ASPECT_SUMMARY_PROMPT", "prompts"),
}

_PROMPT_KEYS = frozenset(attr for attr, _ in _PROMPT_MAP.values())


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
    with _SCHEMA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def parse_remote(raw: dict[str, str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for key, value in raw.items():
        if value is None:
            continue
        try:
            parsed[key] = json.loads(value)
        except json.JSONDecodeError:
            parsed[key] = value
    return parsed


def _module(name: str):
    if name == "settings":
        return sys.modules["app.config.settings"]
    if name == "prompts":
        return sys.modules["app.services.prompts"]
    raise ValueError(f"unknown module: {name}")


def _screaming(value: str) -> str:
    return value.upper()


def _apply_flat_prefix(data: dict, bind: dict) -> None:
    target = _module(bind["module"])
    prefix = bind["prefix"]
    cast = bind.get("cast")
    for field_name, value in data.items():
        if value is None:
            continue
        try:
            val = int(value) if cast == "int" else value
            setattr(target, f"{prefix}{_screaming(field_name)}", val)
        except (TypeError, ValueError):
            logger.warning(
                "[remote_config] invalid int %s.%s", bind.get("prefix"), field_name
            )


def _apply_group_field(data: dict, bind: dict) -> None:
    target = _module(bind["module"])
    for group, group_data in data.items():
        if not isinstance(group_data, dict):
            continue
        group_key = _screaming(group)
        for field_name, value in group_data.items():
            if value is None:
                continue
            setattr(target, f"{group_key}_{_screaming(field_name)}", value)


def _apply_provider(data: dict, bind: dict) -> None:
    target = _module(bind["module"])
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
                setattr(target, attr, int(value) if field_name in int_fields else value)
            except (TypeError, ValueError):
                pass


def _apply_service(data: dict, bind: dict) -> None:
    target = _module(bind["module"])
    for service, service_data in data.items():
        if not isinstance(service_data, dict):
            continue
        prefix = _screaming(service)
        for field_name, value in service_data.items():
            if value is None:
                continue
            setattr(target, f"{prefix}_{_screaming(field_name)}", value)


def _apply_rate_limit_apis(data: dict, bind: dict) -> None:
    target = _module(bind["module"])
    for name, value in (data.get("apis") or {}).items():
        if value:
            setattr(target, f"{_screaming(name)}_RATE_LIMIT", value)


def _apply_mirror(data: dict, mirror: list[dict]) -> None:
    for rule in mirror:
        group_data = data.get(rule["group"]) or {}
        value = group_data.get(rule["field"]) if isinstance(group_data, dict) else None
        if value is None:
            continue
        setattr(_module(rule["module"]), rule["attr"], value)


def _store_runtime(key: str, data: Any, key_schema: dict) -> None:
    store = key_schema.get("store")
    if not store or data is None:
        return
    if store == "agent" and isinstance(data, dict):
        known = {item.name for item in fields(AgentConfig)}
        runtime.agent = AgentConfig(
            **{k: int(v) for k, v in data.items() if k in known and v is not None}
        )
    elif store in {"models", "prompts", "services", "rate_limit"} and isinstance(
        data, dict
    ):
        setattr(runtime, store, data)


_BINDERS: dict[str, Callable[..., None]] = {
    "flat_prefix": _apply_flat_prefix,
    "group_field": _apply_group_field,
    "provider": _apply_provider,
    "service": _apply_service,
    "rate_limit_apis": _apply_rate_limit_apis,
}


def apply_schema(parsed: dict[str, Any], schema: dict[str, Any]) -> None:
    for key, key_schema in schema.get("keys", {}).items():
        data = parsed.get(key)
        if data is None:
            continue
        bind = key_schema.get("bind") or {}
        bind_type = bind.get("type")
        if bind_type in _BINDERS and isinstance(data, dict):
            _BINDERS[bind_type](data, bind)
        mirror = key_schema.get("mirror")
        if mirror and isinstance(data, dict):
            _apply_mirror(data, mirror)
        _store_runtime(key, data, key_schema)


def value_for_required(key: str) -> str | int:
    if key in _PROMPT_KEYS and key != "AGENT_SYSTEM":
        return getattr(prompts, key, "")
    return getattr(settings, key, "")


def validate_required(schema: dict[str, Any]) -> None:
    missing: list[str] = []
    for key in schema.get("required") or []:
        val = value_for_required(key)
        if isinstance(val, int):
            if val <= 0 and key in {"AGENT_MAX_ITER", "OPENAI_MAX_TOKENS"}:
                missing.append(key)
        elif not str(val).strip():
            missing.append(key)
    if missing:
        raise RuntimeError(
            "Thiếu config trên Supabase (bảng config): " + ", ".join(sorted(missing))
        )
