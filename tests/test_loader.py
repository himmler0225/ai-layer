import pytest

from app.config.defaults import build_prompt_defaults, build_settings_defaults, load_schema
from app.config.loader import runtime, validate_required
from app.exceptions import AiLayerConfigError
from tests.conftest import set_provider_remote


def _fill_base_required(schema, settings, prompts):
    settings._REMOTE.clear()
    settings._REMOTE.update(build_settings_defaults(schema))
    prompts._VALUES.clear()
    prompts._VALUES.update(build_prompt_defaults(schema))

    for key in schema.get("required", []):
        if key.endswith("_API_KEY"):
            settings._REMOTE[key] = "test-key"
        elif key.endswith("_MODEL") or key in {"DATA_MINER_URL", "DATA_MINER_KEY"}:
            settings._REMOTE[key] = "configured"
        elif key.endswith("_SYSTEM") or key.endswith("_PROMPT"):
            prompts._VALUES[key] = "configured"

    prompts._VALUES["AGENT_SYSTEM"] = "configured"
    settings._REMOTE["AGENT_SYSTEM"] = "configured"
    settings._REMOTE["AGENT_MAX_ITER"] = 8


def test_validate_required_raises_when_active_provider_key_missing(monkeypatch):
    schema = load_schema()
    import app.config.settings as settings
    import app.services.prompts as prompts

    _fill_base_required(schema, settings, prompts)
    monkeypatch.setattr(runtime, "active_provider", "acme")
    set_provider_remote(settings, "acme", schema, api_key="")

    with pytest.raises(AiLayerConfigError, match="ACME_API_KEY"):
        validate_required(schema)


def test_validate_required_only_checks_active_provider(monkeypatch):
    schema = load_schema()
    import app.config.settings as settings
    import app.services.prompts as prompts

    _fill_base_required(schema, settings, prompts)
    monkeypatch.setattr(runtime, "active_provider", "acme")
    set_provider_remote(settings, "acme", schema)

    validate_required(schema)


def test_validate_required_requires_is_active_when_multiple_providers(monkeypatch):
    schema = load_schema()
    import app.config.settings as settings
    import app.services.prompts as prompts

    _fill_base_required(schema, settings, prompts)
    monkeypatch.setattr(runtime, "active_provider", None)
    monkeypatch.setattr(
        runtime,
        "models",
        [{"id": "acme"}, {"id": "beta"}],
    )
    set_provider_remote(settings, "acme", schema)
    set_provider_remote(settings, "beta", schema)

    with pytest.raises(AiLayerConfigError, match="AI_MODELS.is_active"):
        validate_required(schema)
