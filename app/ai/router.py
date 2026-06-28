"""Router — map task → provider + model."""

from __future__ import annotations

from typing import Optional, Tuple

import app.config.settings as settings
from app.ai.base import BaseLLM
from app.ai.factory import LLMFactory

# Task names — dùng xuyên suốt app thay vì hardcode provider
TASK_AGENT_TOOL = "agent_tool"
TASK_AGENT_SYNTH = "agent_synth"
TASK_ASPECT_GROUP = "aspect_group"
TASK_ASPECT_SUMMARY = "aspect_summary"
TASK_REVIEW_SUMMARY = "review_summary"
TASK_EMBEDDING = "embedding"
TASK_DEFAULT = "default"

# (provider, model_override) — model None → lấy từ settings
TASK_ROUTES: dict[str, Tuple[str, Optional[str]]] = {
    TASK_AGENT_TOOL: ("deepseek", None),
    TASK_AGENT_SYNTH: ("openai", None),
    TASK_ASPECT_GROUP: ("deepseek", None),
    TASK_ASPECT_SUMMARY: ("deepseek", None),
    TASK_REVIEW_SUMMARY: ("openai", None),
    TASK_EMBEDDING: ("openai", None),
    TASK_DEFAULT: ("openai", None),
}


def resolve(task: str) -> Tuple[str, str]:
    """Trả (provider_name, model) cho task."""
    provider, model_override = TASK_ROUTES.get(task, TASK_ROUTES[TASK_DEFAULT])
    model = model_override or _model_for_task(task, provider)
    return provider, model


def _model_for_task(task: str, provider: str) -> str:
    if provider == "deepseek":
        if task == TASK_AGENT_TOOL:
            return (
                settings.DEEP_SEEK_TOOL_MODEL
                or settings.DEEP_SEEK_MODEL
                or "deepseek-chat"
            )
        return (
            settings.DEEP_SEEK_TOOL_MODEL or settings.DEEP_SEEK_MODEL or "deepseek-chat"
        )

    if task == TASK_AGENT_SYNTH:
        return settings.OPENAI_MODEL
    if task in (TASK_ASPECT_GROUP, TASK_ASPECT_SUMMARY):
        return settings.OPENAI_TOOL_MODEL or settings.OPENAI_MODEL
    return settings.OPENAI_MODEL


def max_tokens_for_task(task: str) -> int:
    if task == TASK_AGENT_TOOL:
        return settings.OPENAI_TOOL_MAX_TOKENS or settings.OPENAI_MAX_TOKENS or 4096
    if task in (TASK_ASPECT_GROUP, TASK_ASPECT_SUMMARY):
        return settings.OPENAI_TOOL_MAX_TOKENS or settings.OPENAI_MAX_TOKENS or 4096
    return settings.OPENAI_MAX_TOKENS or 4096


class LLMRouter:
    """Điểm gọi LLM duy nhất — chọn provider theo task."""

    def provider_for(self, task: str) -> BaseLLM:
        provider_name, _ = resolve(task)
        return LLMFactory.get(provider_name)

    async def complete(
        self,
        task: str,
        *,
        user_prompt: str,
        system_prompt: str = "",
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> str:
        _, resolved_model = resolve(task)
        provider = self.provider_for(task)
        return await provider.complete(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            model=model or resolved_model,
            max_tokens=max_tokens or max_tokens_for_task(task),
        )

    async def complete_json(
        self,
        task: str,
        *,
        user_prompt: str,
        system_prompt: str = "",
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> str:
        _, resolved_model = resolve(task)
        provider = self.provider_for(task)
        return await provider.complete_json(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            model=model or resolved_model,
            max_tokens=max_tokens or max_tokens_for_task(task),
        )

    async def create_response(self, task: str, **kwargs):
        _, resolved_model = resolve(task)
        kwargs.setdefault("model", resolved_model)
        kwargs.setdefault("max_output_tokens", max_tokens_for_task(task))
        provider = self.provider_for(task)
        return await provider.create_response(**kwargs)

    def response_stream(self, task: str, **kwargs):
        _, resolved_model = resolve(task)
        kwargs.setdefault("model", resolved_model)
        kwargs.setdefault("max_output_tokens", max_tokens_for_task(task))
        provider = self.provider_for(task)
        return provider.response_stream(**kwargs)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        provider = self.provider_for(TASK_EMBEDDING)
        return await provider.embed_texts(texts)


_router: LLMRouter | None = None


def get_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
