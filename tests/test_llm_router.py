import app.config.settings as settings
from app.ai.router import (TASK_AGENT_SYNTH, TASK_AGENT_TOOL,
                           TASK_ASPECT_GROUP, TASK_ASPECT_SUMMARY,
                           TASK_EMBEDDING, resolve)
import app.services.agent.config as config


def test_router_agent_tool_uses_deepseek():
    provider, _ = resolve(TASK_AGENT_TOOL)
    assert provider == "deepseek"


def test_router_agent_synth_uses_openai():
    provider, _ = resolve(TASK_AGENT_SYNTH)
    assert provider == "openai"


def test_router_embedding_uses_openai():
    provider, _ = resolve(TASK_EMBEDDING)
    assert provider == "openai"


def test_router_aspect_tasks_use_deepseek():
    for task in (TASK_ASPECT_GROUP, TASK_ASPECT_SUMMARY):
        provider, _ = resolve(task)
        assert provider == "deepseek"


def test_dual_mode_when_providers_differ(monkeypatch):
    monkeypatch.setattr(settings, "DEEP_SEEK_MODEL", "deepseek-chat")
    monkeypatch.setattr(settings, "DEEP_SEEK_TOOL_MODEL", "deepseek-chat")
    monkeypatch.setattr(settings, "OPENAI_MODEL", "gpt-4o")
    assert config.dual_mode() is True


def test_dual_mode_off_when_same_provider(monkeypatch):
    monkeypatch.setattr(settings, "XAH_MODEL", "deepseek-chat")
    monkeypatch.setattr(settings, "XAH_TOOL_MODEL", "deepseek-chat")
    import app.ai.router as router_mod

    original_tool = router_mod.TASK_ROUTES[TASK_AGENT_TOOL]
    original_synth = router_mod.TASK_ROUTES[TASK_AGENT_SYNTH]
    router_mod.TASK_ROUTES[TASK_AGENT_TOOL] = ("xah", None)
    router_mod.TASK_ROUTES[TASK_AGENT_SYNTH] = ("xah", None)
    try:
        assert config.dual_mode() is False
    finally:
        router_mod.TASK_ROUTES[TASK_AGENT_TOOL] = original_tool
        router_mod.TASK_ROUTES[TASK_AGENT_SYNTH] = original_synth
