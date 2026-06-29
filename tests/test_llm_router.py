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
import app.services.agent.config as config

_OPENAI_DISABLED = "openai tạm tắt trong PROVIDER_SPECS"
_XAH_DISABLED = "xah tạm tắt trong PROVIDER_SPECS"


def test_router_legacy_agent_tool_uses_deepseek(monkeypatch):
    monkeypatch.setattr(settings, "LLM_DEFAULT_PROVIDER", "")
    provider, _ = resolve(TASK_AGENT_TOOL)
    assert provider == "deepseek"


@pytest.mark.skip(reason=_OPENAI_DISABLED)
def test_router_legacy_agent_synth_uses_openai(monkeypatch):
    monkeypatch.setattr(settings, "LLM_DEFAULT_PROVIDER", "")
    provider, _ = resolve(TASK_AGENT_SYNTH)
    assert provider == "openai"


@pytest.mark.skip(reason=_OPENAI_DISABLED)
def test_router_legacy_embedding_uses_openai(monkeypatch):
    monkeypatch.setattr(settings, "LLM_DEFAULT_PROVIDER", "")
    provider, _ = resolve(TASK_EMBEDDING)
    assert provider == "openai"


def test_router_default_provider_deepseek(monkeypatch):
    monkeypatch.setattr(settings, "LLM_DEFAULT_PROVIDER", "deepseek")
    monkeypatch.setattr(settings, "LLM_EMBEDDING_PROVIDER", "")
    for task in (
        TASK_AGENT_TOOL,
        TASK_AGENT_SYNTH,
        TASK_ASPECT_GROUP,
        TASK_ASPECT_SUMMARY,
        TASK_EMBEDDING,
    ):
        provider, _ = resolve(task)
        assert provider == "deepseek"


@pytest.mark.skip(reason=_XAH_DISABLED)
def test_router_default_provider_xah(monkeypatch):
    monkeypatch.setattr(settings, "LLM_DEFAULT_PROVIDER", "xah")
    monkeypatch.setattr(settings, "LLM_EMBEDDING_PROVIDER", "")
    for task in (
        TASK_AGENT_TOOL,
        TASK_AGENT_SYNTH,
        TASK_ASPECT_GROUP,
        TASK_ASPECT_SUMMARY,
        TASK_EMBEDDING,
    ):
        provider, _ = resolve(task)
        assert provider == "xah"


@pytest.mark.skip(reason=_OPENAI_DISABLED)
def test_router_embedding_provider_override(monkeypatch):
    monkeypatch.setattr(settings, "LLM_DEFAULT_PROVIDER", "deepseek")
    monkeypatch.setattr(settings, "LLM_EMBEDDING_PROVIDER", "openai")
    assert resolve(TASK_AGENT_TOOL)[0] == "deepseek"
    assert resolve(TASK_EMBEDDING)[0] == "openai"


@pytest.mark.skip(reason=_OPENAI_DISABLED)
def test_dual_mode_when_providers_differ(monkeypatch):
    monkeypatch.setattr(settings, "LLM_DEFAULT_PROVIDER", "")
    monkeypatch.setattr(settings, "DEEP_SEEK_MODEL", "deepseek-chat")
    monkeypatch.setattr(settings, "DEEP_SEEK_TOOL_MODEL", "deepseek-chat")
    monkeypatch.setattr(settings, "OPENAI_MODEL", "gpt-4o")
    assert config.dual_mode() is True


def test_dual_mode_off_when_same_provider_and_model(monkeypatch):
    monkeypatch.setattr(settings, "LLM_DEFAULT_PROVIDER", "deepseek")
    monkeypatch.setattr(settings, "DEEP_SEEK_MODEL", "deepseek-chat")
    monkeypatch.setattr(settings, "DEEP_SEEK_TOOL_MODEL", "deepseek-chat")
    assert config.dual_mode() is False


def test_dual_mode_on_when_same_provider_different_models(monkeypatch):
    monkeypatch.setattr(settings, "LLM_DEFAULT_PROVIDER", "deepseek")
    monkeypatch.setattr(settings, "DEEP_SEEK_MODEL", "deepseek-reasoner")
    monkeypatch.setattr(settings, "DEEP_SEEK_TOOL_MODEL", "deepseek-chat")
    assert config.dual_mode() is True
