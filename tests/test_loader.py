import pytest

from app.config.defaults import build_prompt_defaults, build_settings_defaults, load_schema
from app.config.loader import validate_required
from app.exceptions import AiLayerConfigError


def test_validate_required_raises_when_openai_key_missing(monkeypatch):
    schema = load_schema()
    import app.config.settings as settings
    import app.services.prompts as prompts

    settings._REMOTE.clear()
    settings._REMOTE.update(build_settings_defaults(schema))
    prompts._VALUES.clear()
    prompts._VALUES.update(build_prompt_defaults(schema))

    for key in schema.get("required", []):
        if key.endswith("_API_KEY"):
            settings._REMOTE[key] = "test-key"
        elif key.endswith("_MODEL") or key in {"DATA_MINER_URL", "DATA_MINER_KEY"}:
            settings._REMOTE[key] = "configured"
        elif key.endswith("_SYSTEM") or key.endswith("_PROMPT") or key == "AGENT_SYSTEM":
            prompts._VALUES[key] = "configured"

    settings._REMOTE["OPENAI_API_KEY"] = ""
    with pytest.raises(AiLayerConfigError, match="Missing Supabase config keys"):
        validate_required(schema)
