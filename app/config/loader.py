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
from app.config.logger import Logger, log_event
from app.exceptions import AiLayerConfigError, AiLayerValidationError

logger = Logger.get(__name__)


@dataclass
class AgentConfig:
    """Runtime-tunable limits for the agent loop (iteration count, comment/result truncation)."""

    max_iter: int = 0
    max_comments: int = 0
    max_comment_len: int = 0
    max_list_items: int = 0
    max_result_chars: int = 0


@dataclass
class RuntimeConfig:
    """In-memory snapshot of remote-configurable runtime settings: agent limits,
    the model list/active provider, prompts, services, and rate limits."""

    agent: AgentConfig = field(default_factory=AgentConfig)
    models: list[dict[str, Any]] = field(default_factory=list)
    active_provider: str | None = None
    prompts: dict[str, Any] = field(default_factory=dict)
    services: dict[str, Any] = field(default_factory=dict)
    rate_limit: dict[str, Any] = field(default_factory=dict)


runtime = RuntimeConfig()
config_parse_errors: dict[str, str] = {}


def load_schema() -> dict[str, Any]:
    """Load the remote-config schema (re-exported from `app.config.defaults`).

    Returns:
        dict[str, Any]: The parsed remote-config schema.
    """
    return _load_schema()


def parse_remote(raw: dict[str, str]) -> dict[str, Any]:
    """Parse raw remote-config values (JSON-encoded strings) into Python objects.

    Invalid JSON is recorded in `config_parse_errors` (keyed by config key) and
    the raw string is kept as a fallback value.

    Args:
        raw: Mapping of config key to its raw JSON-encoded string value.

    Returns:
        dict[str, Any]: Mapping of config key to its parsed value.
    """
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
            logger.error(log_event("remote_config", "json invalid", key=key, error=exc))
    return parsed


def _screaming(value: str) -> str:
    """Convert a field name to SCREAMING_CASE for use as a settings/prompt attribute suffix.

    Args:
        value: Lowercase (or mixed-case) field name.

    Returns:
        str: The uppercased value.
    """
    return value.upper()


def _set_module_value(module: str, attr: str, value: Any) -> None:
    """Write a resolved config value into the target module (`settings` or `prompts`).

    Args:
        module: Target module name, either "settings" or "prompts".
        attr: Attribute/key name to set on that module.
        value: Value to store.

    Raises:
        AiLayerValidationError: If `module` is neither "settings" nor "prompts".
    """
    if module == "settings":
        settings.set_remote(attr, value)
    elif module == "prompts":
        prompts.set_prompt(attr, str(value))
    else:
        raise AiLayerValidationError(f"unknown module: {module}")


def _apply_flat_prefix(data: dict, bind: dict, key_schema: dict) -> None:
    """Apply a "flat_prefix" bind: write each field of `data` to `settings` as
    `{prefix}{FIELD_NAME}`, casting to bool/int as declared by the schema.

    Args:
        data: Parsed config values for this key.
        bind: The key's `bind` schema block (prefix, cast, module).
        key_schema: The full schema entry for this key (used for `fields`/`bool_fields`).
    """
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
            logger.warning(log_event("remote_config", "invalid value", scope=f"{prefix}.{field_name}"))


def _apply_group_field(data: dict, bind: dict) -> None:
    """Apply a "group_field" bind: for each group in `data`, write its fields to
    the target module as `{GROUP}_{FIELD_NAME}`.

    Args:
        data: Mapping of group name to a dict of field values.
        bind: The key's `bind` schema block (module).
    """
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
    """Coerce a raw config value (bool, string, or other) to a boolean.

    Args:
        value: Value to coerce; strings are matched case-insensitively against
            truthy tokens ("1", "true", "yes", "on").

    Returns:
        bool: The coerced boolean value.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def resolve_active_provider(data: dict | list) -> str | None:
    """Find the provider with `is_active: true` in AI_MODELS (returns the first match only).

    Args:
        data: AI_MODELS config, either a list of provider dicts or a legacy
            `{provider_id: {...}}` mapping.

    Returns:
        str | None: The lowercased active provider id, or None if none is active.
    """
    for provider_id, cfg in _normalize_provider_map(data).items():
        if isinstance(cfg, dict) and _coerce_bool(cfg.get("is_active")):
            return str(provider_id).strip().lower()
    return None


def _normalize_provider_map(data: dict | list) -> dict[str, dict]:
    """Normalize AI_MODELS from either the array form `[{id, ...}, ...]` or the
    legacy object form `{id: {...}}` into a `{provider_id: fields}` map.

    Args:
        data: Raw AI_MODELS config, as a list or a dict.

    Returns:
        dict[str, dict]: Mapping of lowercased provider id to its field dict.
    """
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
    """Apply a "provider" bind: write each provider's fields to `settings` as
    `{PREFIX}_{FIELD_NAME}`, casting declared int fields and skipping declared
    skip fields.

    Args:
        data: AI_MODELS config (list or legacy dict form).
        bind: The key's `bind` schema block (providers map, int_fields, skip_fields, module).
    """
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
    """Apply a "service" bind: write each service's fields to `settings` as
    `{SERVICE}_{FIELD_NAME}`, casting to the type declared in the schema.

    Args:
        data: Mapping of service name to a dict of field values.
        bind: The key's `bind` schema block (services type map, module).
    """
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
    """Apply a "rate_limit_apis" bind: write each API's rate-limit string to
    `settings` as `{API}_RATE_LIMIT`.

    Args:
        data: Rate-limit config, either `{"apis": {name: limit}}` or `{name: limit}` directly.
        bind: The key's `bind` schema block (apis list, module).
    """
    apis = bind.get("apis") or list((data.get("apis") or {}).keys())
    source = data.get("apis") or data
    for name in apis:
        val = source.get(name)
        if val:
            _set_module_value(bind["module"], f"{_screaming(name)}_RATE_LIMIT", val)


def _apply_mirror(data: dict, mirror: list[dict]) -> None:
    """Apply mirror rules that copy a nested group/field value to a flat module attribute.

    Args:
        data: Parsed config values for this key.
        mirror: List of mirror rules, each with `group`, `field`, `module`, and `attr`.
    """
    for rule in mirror:
        group_data = data.get(rule["group"]) or {}
        value = group_data.get(rule["field"]) if isinstance(group_data, dict) else None
        if value is None:
            continue
        _set_module_value(rule["module"], rule["attr"], value)


def _store_runtime(key: str, data: Any, key_schema: dict) -> None:
    """Cache a config key's parsed value onto the module-level `runtime` object.

    Handles the special "agent" (builds an `AgentConfig`), "models" (normalizes
    and resolves the active provider), and "prompts"/"services"/"rate_limit" stores.

    Args:
        key: The config key name (routing is driven by `key_schema`, not `key`).
        data: The parsed value for this key.
        key_schema: The schema entry for this key; `key_schema["store"]` selects
            which `runtime` attribute (if any) to populate.
    """
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
    """Enumerate all settings-style keys (`{GROUP}_{FIELD}`) declared under PROMPTS.

    Args:
        schema: The parsed remote-config schema.

    Returns:
        frozenset[str]: The set of prompt key names.
    """
    prompt_cfg = schema.get("keys", {}).get("PROMPTS") or {}
    keys: set[str] = set()
    for group, field_list in (prompt_cfg.get("groups") or {}).items():
        group_key = _screaming(group)
        for field_name in field_list:
            keys.add(f"{group_key}_{_screaming(field_name)}")
    return frozenset(keys)


def apply_schema(parsed: dict[str, Any], schema: dict[str, Any]) -> None:
    """Apply a full parsed remote config to `settings`/`prompts`/`runtime`.

    Dispatches each schema key to its bind handler and mirror rules, then resets
    the LLM factory so subsequent calls pick up the new provider config.

    Args:
        parsed: Parsed remote config values, keyed by config key (see `parse_remote`).
        schema: The parsed remote-config schema.
    """
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
    """Resolve the current value of a required config key.

    Checks `prompts` first for prompt keys (other than AGENT_SYSTEM), and
    `settings` otherwise.

    Args:
        key: The required config key name.
        schema: The parsed remote-config schema.

    Returns:
        str | int: The current value, or "" if unset.
    """
    if key in _prompt_keys(schema) and key != "AGENT_SYSTEM":
        return getattr(prompts, key, "")
    return getattr(settings, key, "")


def _provider_prefix_map(schema: dict[str, Any]) -> dict[str, str]:
    """Read the AI_MODELS provider-id to settings-prefix map from the schema.

    Args:
        schema: The parsed remote-config schema.

    Returns:
        dict[str, str]: Mapping of provider id to its settings prefix.
    """
    bind = (schema.get("keys", {}).get("AI_MODELS") or {}).get("bind") or {}
    return bind.get("providers") or {}


def provider_settings_prefix(provider_id: str, schema: dict[str, Any] | None = None) -> str:
    """Map a provider id (e.g. "deepseek") to its settings prefix (e.g. "DEEP_SEEK").

    Args:
        provider_id: Provider id as used in AI_MODELS.
        schema: Remote-config schema to consult; loaded via `load_schema()` if omitted.

    Returns:
        str: The settings prefix for the provider, falling back to its
        uppercased id if not explicitly mapped.
    """
    if schema is None:
        schema = load_schema()
    key = (provider_id or "").strip().lower()
    return _provider_prefix_map(schema).get(key, _screaming(key))


def _provider_required_setting_keys(prefix: str) -> list[str]:
    """List the settings keys required for a given LLM provider prefix.

    Args:
        prefix: Settings prefix for the provider (e.g. "DEEP_SEEK").

    Returns:
        list[str]: The `{PREFIX}_API_KEY`, `_BASE_URL`, `_MODEL`, `_MAX_TOKENS`,
        `_TOOL_MODEL`, and `_TOOL_MAX_TOKENS` key names.
    """
    return [
        f"{prefix}_API_KEY",
        f"{prefix}_BASE_URL",
        f"{prefix}_MODEL",
        f"{prefix}_MAX_TOKENS",
        f"{prefix}_TOOL_MODEL",
        f"{prefix}_TOOL_MAX_TOKENS",
    ]


def _all_provider_setting_keys(schema: dict[str, Any]) -> set[str]:
    """Collect the required settings keys for every provider known to the schema
    or currently present in `runtime.models`.

    Args:
        schema: The parsed remote-config schema.

    Returns:
        set[str]: Union of required settings keys across all known providers.
    """
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
    """List provider settings prefixes that currently have a non-empty API key configured.

    Args:
        schema: The parsed remote-config schema.

    Returns:
        list[str]: Settings prefixes (e.g. "OPENAI") that have an API key set.
    """
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
    """Determine which provider's settings prefix should be validated: the active
    provider if one is set, otherwise the single configured provider if there's
    exactly one.

    Args:
        schema: The parsed remote-config schema.

    Returns:
        str | None: The settings prefix to validate, or None if ambiguous/unset.
    """
    active = (runtime.active_provider or "").strip().lower()
    if active:
        return provider_settings_prefix(active, schema)
    configured = _configured_provider_prefixes(schema)
    if len(configured) == 1:
        return configured[0]
    return None


def collect_required_keys(schema: dict[str, Any]) -> list[str]:
    """Compute the full list of required config keys: base schema requirements
    plus the currently-active (or uniquely-configured) provider's settings keys.

    Args:
        schema: The parsed remote-config schema.

    Returns:
        list[str]: Required config key names.
    """
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
    """Find missing/invalid config, reported using admin-panel paths (e.g.
    "PROMPTS.agent.system") rather than raw env var names, so operators can find
    them in the admin UI.

    Args:
        schema: The parsed remote-config schema.

    Returns:
        list[str]: Human-readable descriptions of each config gap found.
    """
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
    """Validate that all required config keys are present and well-formed.

    Args:
        schema: The parsed remote-config schema.

    Raises:
        AiLayerConfigError: If any required config keys are missing or invalid,
        listing the offending keys/paths.
    """
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
