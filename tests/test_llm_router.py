import pytest

import app.config.settings as settings
from app.ai.router import (
    TASK_AGENT_SYNTH,
    TASK_AGENT_TOOL,
    TASK_ASPECT_GROUP,
    TASK_ASPECT_SUMMARY,
    TASK_EMBEDDING,
    resolve,
)
from app.config.defaults import load_schema
from app.config.loader import runtime
from app.exceptions import AiLayerConfigError
import app.services.agent.config as config
from tests.conftest import set_provider_remote


def test_router_requires_active_provider(monkeypatch):
    monkeypatch.setattr(runtime, "active_provider", None)
    with pytest.raises(AiLayerConfigError, match="is_active"):
        resolve(TASK_AGENT_TOOL)


def test_router_uses_active_provider(monkeypatch):
    monkeypatch.setattr(runtime, "active_provider", "acme")
    monkeypatch.setattr(settings, "LLM_EMBEDDING_PROVIDER", "")
    for task in (
        TASK_AGENT_TOOL,
        TASK_AGENT_SYNTH,
        TASK_ASPECT_GROUP,
        TASK_ASPECT_SUMMARY,
        TASK_EMBEDDING,
    ):
        provider, _ = resolve(task)
        assert provider == "acme"


def test_router_embedding_provider_override(monkeypatch):
    monkeypatch.setattr(runtime, "active_provider", "acme")
    monkeypatch.setattr(settings, "LLM_EMBEDDING_PROVIDER", "embedco")
    assert resolve(TASK_AGENT_TOOL)[0] == "acme"
    assert resolve(TASK_EMBEDDING)[0] == "embedco"


def test_dual_mode_off_when_same_provider_and_model(monkeypatch):
    schema = load_schema()
    monkeypatch.setattr(runtime, "active_provider", "acme")
    prefix = set_provider_remote(settings, "acme", schema, model="model-a", tool_model="model-a")
    settings._REMOTE[f"{prefix}_MODEL"] = "model-a"
    settings._REMOTE[f"{prefix}_TOOL_MODEL"] = "model-a"
    assert config.dual_mode() is False


def test_dual_mode_on_when_same_provider_different_models(monkeypatch):
    schema = load_schema()
    monkeypatch.setattr(runtime, "active_provider", "acme")
    prefix = set_provider_remote(settings, "acme", schema)
    settings._REMOTE[f"{prefix}_MODEL"] = "model-synth"
    settings._REMOTE[f"{prefix}_TOOL_MODEL"] = "model-tool"
    assert config.dual_mode() is True
