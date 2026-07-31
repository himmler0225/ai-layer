from dataclasses import dataclass, field, fields
from typing import Any
from collections.abc import Callable

import app.config.settings as settings
import app.services.prompts as prompts
from app.config.defaults import (
    apply_env_fallbacks,
    build_prompt_defaults,
    load_schema as _load_schema,
)
from app.config.logger import Logger
from app.exceptions import AiLayerConfigError, AiLayerValidationError

logger = Logger.get(__name__)


@dataclass
class AgentConfig:
    """Lớp `AgentConfig` (kế thừa object)."""

    max_iter: int = 0
    max_comments: int = 0
    max_comment_len: int = 0
    max_list_items: int = 0
    max_result_chars: int = 0


@dataclass
class RuntimeConfig:
    """Lớp `RuntimeConfig` (kế thừa object)."""

    agent: AgentConfig = field(default_factory=AgentConfig)
    models: list[dict[str, Any]] = field(default_factory=list)
    active_provider: str | None = None
    prompts: dict[str, Any] = field(default_factory=dict)
    services: dict[str, Any] = field(default_factory=dict)
    rate_limit: dict[str, Any] = field(default_factory=dict)


runtime = RuntimeConfig()
config_parse_errors: dict[str, str] = {}


def load_schema() -> dict[str, Any]:
    """Tải schema.

    Returns:
        (dict[str, Any]) Kết quả trả về."""
    return _load_schema()


def parse_remote(raw: dict[str, str]) -> dict[str, Any]:
    """Phân tích remote.

    Args:
        raw: (dict[str, str]) Tham số `raw`.

    Returns:
        (dict[str, Any]) Kết quả trả về."""
    import json

    config_parse_errors.clear()
    parsed: dict[str, Any] = {}
    for key, value in raw.items():
        if value is None:
            continue
        try:
            parsed[key] = json.loads(value)
        except json.JSONDecodeError as exc:
            config_parse_errors[key] = str(exc)
            parsed[key] = value
            logger.error("[remote_config] %s JSON invalid: %s", key, exc)
    return parsed


def _screaming(value: str) -> str:
    """(Nội bộ) Screaming `_screaming`.

    Args:
        value: (str) Tham số `value`.

    Returns:
        (str) Kết quả trả về."""
    return value.upper()


def _set_module_value(module: str, attr: str, value: Any) -> None:
    """(Nội bộ) Set module value.

    Args:
        module: (str) Tham số `module`.
        attr: (str) Tham số `attr`.
        value: (Any) Tham số `value`.

    Returns:
        (None) Kết quả trả về."""
    if module == "settings":
        settings.set_remote(attr, value)
    elif module == "prompts":
        prompts.set_prompt(attr, str(value))
    else:
        raise AiLayerValidationError(f"unknown module: {module}")


def _apply_flat_prefix(data: dict, bind: dict, key_schema: dict) -> None:
    """(Nội bộ) Áp dụng flat prefix.

    Args:
        data: (dict) Tham số `data`.
        bind: (dict) Tham số `bind`.
        key_schema: (dict) Tham số `key_schema`.

    Returns:
        (None) Kết quả trả về."""
    prefix = bind["prefix"]
    cast = bind.get("cast")
    bool_fields = set(key_schema.get("bool_fields") or [])
    field_names = key_schema.get("fields") or list(data.keys())
    all_fields = list(dict.fromkeys([*field_names, *bool_fields]))
    for field_name in all_fields:
        if field_name not in data or data[field_name] is None:
            continue
        try:
            if field_name in bool_fields:
                raw = data[field_name]
                if isinstance(raw, str):
                    val = raw.lower() in {"1", "true", "yes", "on"}
                else:
                    val = bool(raw)
            elif cast == "int":
                val = int(data[field_name])
            else:
                val = data[field_name]
            _set_module_value(bind["module"], f"{prefix}{_screaming(field_name)}", val)
        except TypeError, ValueError:
            logger.warning("[remote_config] invalid value %s.%s", prefix, field_name)


def _apply_group_field(data: dict, bind: dict) -> None:
    """(Nội bộ) Áp dụng group field.

    Args:
        data: (dict) Tham số `data`.
        bind: (dict) Tham số `bind`.

    Returns:
        (None) Kết quả trả về."""
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


def _coerce_bool(value: Any) -> bool:
    """(Nội bộ) Coerce bool `_coerce_bool`.

    Args:
        value: (Any) Tham số `value`.

    Returns:
        (bool) Kết quả trả về."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def resolve_active_provider(data: dict | list) -> str | None:
    """Provider có `is_active: true` trong AI_MODELS (chỉ lấy entry đầu tiên)."""
    for provider_id, cfg in _normalize_provider_map(data).items():
        if isinstance(cfg, dict) and _coerce_bool(cfg.get("is_active")):
            return str(provider_id).strip().lower()
    return None


def _normalize_provider_map(data: dict | list) -> dict[str, dict]:
    """Chuyển AI_MODELS dạng mảng `[{id, ...}]` hoặc object legacy `{id: {...}}` thành map."""
    if isinstance(data, list):
        out: dict[str, dict] = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            provider_id = item.get("id") or item.get("provider")
            if not provider_id:
                continue
            key = str(provider_id).strip().lower()
            fields = {k: v for k, v in item.items() if k not in ("id", "provider") and v is not None}
            out[key] = fields
        return out
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if isinstance(v, dict)}
    return {}


def _apply_provider(data: dict | list, bind: dict) -> None:
    """(Nội bộ) Áp dụng provider.

    Args:
        data: (dict | list) Tham số `data`.
        bind: (dict) Tham số `bind`.

    Returns:
        (None) Kết quả trả về."""
    providers = bind.get("providers") or {}
    int_fields = set(bind.get("int_fields") or [])
    skip_fields = set(bind.get("skip_fields") or [])
    for provider, provider_data in _normalize_provider_map(data).items():
        if not isinstance(provider_data, dict):
            continue
        prefix = providers.get(provider, _screaming(provider))
        for field_name, value in provider_data.items():
            if field_name in skip_fields or value is None:
                continue
            attr = f"{prefix}_{_screaming(field_name)}"
            try:
                val = int(value) if field_name in int_fields else value
                _set_module_value(bind["module"], attr, val)
            except TypeError, ValueError:
                pass


def _apply_service(data: dict, bind: dict) -> None:
    """(Nội bộ) Áp dụng service.

    Args:
        data: (dict) Tham số `data`.
        bind: (dict) Tham số `bind`.

    Returns:
        (None) Kết quả trả về."""
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
    """(Nội bộ) Áp dụng rate limit apis.

    Args:
        data: (dict) Tham số `data`.
        bind: (dict) Tham số `bind`.

    Returns:
        (None) Kết quả trả về."""
    apis = bind.get("apis") or list((data.get("apis") or {}).keys())
    source = data.get("apis") or data
    for name in apis:
        val = source.get(name)
        if val:
            _set_module_value(bind["module"], f"{_screaming(name)}_RATE_LIMIT", val)


def _apply_mirror(data: dict, mirror: list[dict]) -> None:
    """(Nội bộ) Áp dụng mirror.

    Args:
        data: (dict) Tham số `data`.
        mirror: (list[dict]) Tham số `mirror`.

    Returns:
        (None) Kết quả trả về."""
    for rule in mirror:
        group_data = data.get(rule["group"]) or {}
        value = group_data.get(rule["field"]) if isinstance(group_data, dict) else None
        if value is None:
            continue
        _set_module_value(rule["module"], rule["attr"], value)


def _store_runtime(key: str, data: Any, key_schema: dict) -> None:
    """(Nội bộ) Lưu runtime.

    Args:
        key: (str) Tham số `key`.
        data: (Any) Tham số `data`.
        key_schema: (dict) Tham số `key_schema`.

    Returns:
        (None) Kết quả trả về."""
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
    elif store == "models":
        if isinstance(data, list):
            runtime.models = [item for item in data if isinstance(item, dict)]
        elif isinstance(data, dict):
            runtime.models = [{"id": k, **v} for k, v in data.items() if isinstance(v, dict)]
        runtime.active_provider = resolve_active_provider(data)
    elif store in {"prompts", "services", "rate_limit"} and isinstance(data, dict):
        setattr(runtime, store, data)


_BINDERS: dict[str, Callable[..., None]] = {
    "group_field": _apply_group_field,
    "provider": _apply_provider,
    "service": _apply_service,
    "rate_limit_apis": _apply_rate_limit_apis,
}


def _prompt_keys(schema: dict[str, Any]) -> frozenset[str]:
    """(Nội bộ) Prompt keys.

    Args:
        schema: (dict[str, Any]) Tham số `schema`.

    Returns:
        (frozenset[str]) Kết quả trả về."""
    prompt_cfg = schema.get("keys", {}).get("PROMPTS") or {}
    keys: set[str] = set()
    for group, field_list in (prompt_cfg.get("groups") or {}).items():
        group_key = _screaming(group)
        for field_name in field_list:
            keys.add(f"{group_key}_{_screaming(field_name)}")
    return frozenset(keys)


def apply_schema(parsed: dict[str, Any], schema: dict[str, Any]) -> None:
    """Áp dụng schema.

    Args:
        parsed: (dict[str, Any]) Tham số `parsed`.
        schema: (dict[str, Any]) Tham số `schema`.

    Returns:
        (None) Kết quả trả về."""
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
        elif bind_type in _BINDERS and (isinstance(data, dict) or (bind_type == "provider" and isinstance(data, list))):
            _BINDERS[bind_type](data, bind)
        mirror = key_schema.get("mirror")
        if mirror and isinstance(data, dict):
            _apply_mirror(data, mirror)
        _store_runtime(key, data, key_schema)

    apply_env_fallbacks(settings._REMOTE, schema)

    from app.ai.factory import LLMFactory

    LLMFactory.reset()


def value_for_required(key: str, schema: dict[str, Any]) -> str | int:
    """Value for required.

    Args:
        key: (str) Tham số `key`.
        schema: (dict[str, Any]) Tham số `schema`.

    Returns:
        (str | int) Kết quả trả về."""
    if key in _prompt_keys(schema) and key != "AGENT_SYSTEM":
        return getattr(prompts, key, "")
    return getattr(settings, key, "")


def _provider_prefix_map(schema: dict[str, Any]) -> dict[str, str]:
    """(Nội bộ) Provider prefix map `_provider_prefix_map`.

    Args:
        schema: (dict[str, Any]) Tham số `schema`.

    Returns:
        (dict[str, str]) Kết quả trả về."""
    bind = (schema.get("keys", {}).get("AI_MODELS") or {}).get("bind") or {}
    return bind.get("providers") or {}


def provider_settings_prefix(provider_id: str, schema: dict[str, Any] | None = None) -> str:
    """Map provider id (vd. deepseek) → settings prefix (vd. DEEP_SEEK)."""
    if schema is None:
        schema = load_schema()
    key = (provider_id or "").strip().lower()
    return _provider_prefix_map(schema).get(key, _screaming(key))


def _provider_required_setting_keys(prefix: str) -> list[str]:
    """(Nội bộ) Provider required setting keys `_provider_required_setting_keys`.

    Args:
        prefix: (str) Tham số `prefix`.

    Returns:
        (list[str]) Kết quả trả về."""
    return [
        f"{prefix}_API_KEY",
        f"{prefix}_BASE_URL",
        f"{prefix}_MODEL",
        f"{prefix}_MAX_TOKENS",
        f"{prefix}_TOOL_MODEL",
        f"{prefix}_TOOL_MAX_TOKENS",
    ]


def _all_provider_setting_keys(schema: dict[str, Any]) -> set[str]:
    """(Nội bộ) All provider setting keys `_all_provider_setting_keys`.

    Args:
        schema: (dict[str, Any]) Tham số `schema`.

    Returns:
        (set[str]) Kết quả trả về."""
    keys: set[str] = set()
    seen_prefixes: set[str] = set()
    for provider_id in _provider_prefix_map(schema):
        prefix = provider_settings_prefix(provider_id, schema)
        if prefix in seen_prefixes:
            continue
        seen_prefixes.add(prefix)
        keys.update(_provider_required_setting_keys(prefix))
    for item in runtime.models:
        if not isinstance(item, dict):
            continue
        provider_id = item.get("id")
        if not provider_id:
            continue
        prefix = provider_settings_prefix(str(provider_id), schema)
        if prefix in seen_prefixes:
            continue
        seen_prefixes.add(prefix)
        keys.update(_provider_required_setting_keys(prefix))
    return keys


def _configured_provider_prefixes(schema: dict[str, Any]) -> list[str]:
    """(Nội bộ) Configured provider prefixes `_configured_provider_prefixes`.

    Args:
        schema: (dict[str, Any]) Tham số `schema`.

    Returns:
        (list[str]) Kết quả trả về."""
    configured: list[str] = []
    seen: set[str] = set()
    candidates = list(_provider_prefix_map(schema)) + [
        str(item.get("id")) for item in runtime.models if isinstance(item, dict) and item.get("id")
    ]
    for provider_id in candidates:
        prefix = provider_settings_prefix(provider_id, schema)
        if prefix in seen:
            continue
        seen.add(prefix)
        val = getattr(settings, f"{prefix}_API_KEY", None)
        if str(val or "").strip():
            configured.append(prefix)
    return configured


def _resolve_validation_prefix(schema: dict[str, Any]) -> str | None:
    """Prefix settings của provider cần validate (theo is_active hoặc provider duy nhất có key)."""
    active = (runtime.active_provider or "").strip().lower()
    if active:
        return provider_settings_prefix(active, schema)
    configured = _configured_provider_prefixes(schema)
    if len(configured) == 1:
        return configured[0]
    return None


def collect_required_keys(schema: dict[str, Any]) -> list[str]:
    """Danh sách key bắt buộc: base schema + provider đang active."""
    skip = _all_provider_setting_keys(schema)
    keys = [k for k in (schema.get("required") or []) if k not in skip]
    prefix = _resolve_validation_prefix(schema)
    if prefix:
        keys.extend(_provider_required_setting_keys(prefix))
    return keys


_INT_PROVIDER_SUFFIXES = ("_MAX_TOKENS", "_TOOL_MAX_TOKENS")

_LEGACY_REQUIRED_ALIASES = {
    "AGENT_SYSTEM": "PROMPTS.agent.system",
    "DATA_MINER_KEY": "SERVICES.data_miner.key",
    "DATA_MINER_URL": "SERVICES.data_miner.url",
}


def _friendly_config_gaps(schema: dict[str, Any]) -> list[str]:
    """Thiếu config theo đường dẫn admin (dễ sửa hơn tên env)."""
    gaps: list[str] = []
    for key, message in config_parse_errors.items():
        gaps.append(f"{key} (JSON lỗi: {message})")

    agent = (runtime.prompts.get("agent") or {}) if isinstance(runtime.prompts, dict) else {}
    if not str(agent.get("system") or "").strip() and not str(getattr(settings, "AGENT_SYSTEM", "") or "").strip():
        gaps.append("PROMPTS.agent.system")

    services = runtime.services if isinstance(runtime.services, dict) else {}
    data_miner = services.get("data_miner") or {}
    if not isinstance(data_miner, dict):
        data_miner = {}
    if not str(data_miner.get("url") or getattr(settings, "DATA_MINER_URL", "") or "").strip():
        gaps.append("SERVICES.data_miner.url")
    if not str(data_miner.get("key") or getattr(settings, "DATA_MINER_KEY", "") or "").strip():
        gaps.append("SERVICES.data_miner.key")

    if "AI_MODELS" in config_parse_errors:
        return gaps

    if runtime.models and not runtime.active_provider:
        gaps.append("AI_MODELS.is_active (chọn đúng một provider)")

    return gaps


def validate_required(schema: dict[str, Any]) -> None:
    """Kiểm tra required.

    Args:
        schema: (dict[str, Any]) Tham số `schema`.

    Returns:
        (None) Kết quả trả về."""
    missing: list[str] = list(_friendly_config_gaps(schema))
    skip_keys = {
        "AGENT_SYSTEM",
        "DATA_MINER_KEY",
        "DATA_MINER_URL",
    }

    active = (runtime.active_provider or "").strip().lower()
    configured = _configured_provider_prefixes(schema)
    if not config_parse_errors.get("AI_MODELS") and active and not _resolve_validation_prefix(schema):
        missing.append(f"AI_MODELS.is_active ({active})")
    elif not config_parse_errors.get("AI_MODELS") and not _resolve_validation_prefix(schema) and len(configured) > 1:
        missing.append("AI_MODELS.is_active")

    for key in collect_required_keys(schema):
        if key in skip_keys:
            continue
        val = value_for_required(key, schema)
        if key.endswith(_INT_PROVIDER_SUFFIXES) or key == "AGENT_MAX_ITER":
            if not isinstance(val, int) or val <= 0:
                missing.append(_LEGACY_REQUIRED_ALIASES.get(key, key))
        elif not str(val).strip():
            missing.append(_LEGACY_REQUIRED_ALIASES.get(key, key))
    if missing:
        raise AiLayerConfigError("Missing Supabase config keys: " + ", ".join(sorted(set(missing))))
