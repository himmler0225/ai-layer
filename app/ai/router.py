from __future__ import annotations

from typing import Any, Optional, Tuple

import app.config.settings as settings
from app.ai.base import BaseLLM
from app.ai.factory import LLMFactory
from app.ai.providers import get_provider_spec, normalize_provider

TASK_AGENT_TOOL = "agent_tool"
TASK_AGENT_SYNTH = "agent_synth"
TASK_ASPECT_GROUP = "aspect_group"
TASK_ASPECT_SUMMARY = "aspect_summary"
TASK_REVIEW_SUMMARY = "review_summary"
TASK_EMBEDDING = "embedding"
TASK_DEFAULT = "default"

# Legacy routing khi không set settings.LLM_DEFAULT_PROVIDER (env LLM_DEFAULT_PROVIDER).
_LEGACY_ROUTES: dict[str, str] = {
    TASK_AGENT_TOOL: "deepseek",
    TASK_AGENT_SYNTH: "openai",
    TASK_ASPECT_GROUP: "deepseek",
    TASK_ASPECT_SUMMARY: "deepseek",
    TASK_REVIEW_SUMMARY: "openai",
    TASK_EMBEDDING: "openai",
    TASK_DEFAULT: "openai",
}

TASK_ROUTES: dict[str, Tuple[Optional[str], Optional[str]]] = {
    task: (None, None) for task in _LEGACY_ROUTES
}


def _resolve_provider(task: str) -> str:
    """Chọn provider theo env LLM_DEFAULT_PROVIDER hoặc legacy map."""
    default = (settings.LLM_DEFAULT_PROVIDER or "").strip()
    if default:
        if task == TASK_EMBEDDING:
            emb = (settings.LLM_EMBEDDING_PROVIDER or "").strip()
            return normalize_provider(emb or default)
        return normalize_provider(default)
    explicit, _ = TASK_ROUTES.get(task, TASK_ROUTES[TASK_DEFAULT])
    if explicit:
        return normalize_provider(explicit)
    return normalize_provider(_LEGACY_ROUTES.get(task, _LEGACY_ROUTES[TASK_DEFAULT]))


def _setting(prefix: str, field: str, default: Any = None) -> Any:
    """(Nội bộ) Setting `_setting`.

    Args:
        prefix: (str) Tham số `prefix`.
        field: (str) Tham số `field`.
        default: (Any, mặc định None) Tham số `default`.

    Returns:
        (Any) Kết quả trả về."""
    value = getattr(settings, f"{prefix}_{field}", None)
    return value if value not in (None, "", 0) else default


def resolve(task: str) -> Tuple[str, str]:
    """Giải quyết `resolve`.

    Args:
        task: (str) Tham số `task`.

    Returns:
        (Tuple[str, str]) Kết quả trả về."""
    _, model_override = TASK_ROUTES.get(task, TASK_ROUTES[TASK_DEFAULT])
    provider = _resolve_provider(task)
    model = model_override or _model_for_task(task, provider)
    return (provider, model)


def _model_for_task(task: str, provider: str) -> str:
    """(Nội bộ) Model for task.

    Args:
        task: (str) Tham số `task`.
        provider: (str) Tham số `provider`.

    Returns:
        (str) Kết quả trả về."""
    spec = get_provider_spec(provider)
    tool_model = _setting(spec.settings_prefix, "TOOL_MODEL")
    model = _setting(spec.settings_prefix, "MODEL", spec.fallback_model)
    if task == TASK_AGENT_TOOL:
        return tool_model or model
    if task == TASK_AGENT_SYNTH:
        return model
    if task in (TASK_ASPECT_GROUP, TASK_ASPECT_SUMMARY):
        return tool_model or model
    return model


def max_tokens_for_task(task: str) -> int:
    """Max tokens for task.

    Args:
        task: (str) Tham số `task`.

    Returns:
        (int) Kết quả trả về."""
    provider, _ = resolve(task)
    spec = get_provider_spec(provider)
    tool_max = _setting(spec.settings_prefix, "TOOL_MAX_TOKENS")
    max_tokens = _setting(spec.settings_prefix, "MAX_TOKENS")
    if task in (TASK_AGENT_TOOL, TASK_ASPECT_GROUP, TASK_ASPECT_SUMMARY):
        return tool_max or max_tokens or 4096
    return max_tokens or 4096


class LLMRouter:
    """    Lớp `LLMRouter` (kế thừa object)."""
    def provider_for(self, task: str) -> BaseLLM:
        """Provider for.

    Args:
        task: (str) Tham số `task`.

    Returns:
        (BaseLLM) Kết quả trả về."""
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
        """Hoàn tất `complete` (async).

    Args:
        task: (str) Tham số `task`.
        user_prompt: (str) Tham số `user_prompt`.
        system_prompt: (str, mặc định '') Tham số `system_prompt`.
        max_tokens: (Optional[int], mặc định None) Tham số `max_tokens`.
        model: (Optional[str], mặc định None) Tham số `model`.

    Returns:
        (str) Kết quả trả về."""
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
        """Hoàn tất json (async).

    Args:
        task: (str) Tham số `task`.
        user_prompt: (str) Tham số `user_prompt`.
        system_prompt: (str, mặc định '') Tham số `system_prompt`.
        max_tokens: (Optional[int], mặc định None) Tham số `max_tokens`.
        model: (Optional[str], mặc định None) Tham số `model`.

    Returns:
        (str) Kết quả trả về."""
        _, resolved_model = resolve(task)
        provider = self.provider_for(task)
        return await provider.complete_json(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            model=model or resolved_model,
            max_tokens=max_tokens or max_tokens_for_task(task),
        )

    async def create_response(self, task: str, **kwargs):
        """Tạo response (async).

    Args:
        task: (str) Tham số `task`.
        kwargs: (Any) Tham số `kwargs`."""
        _, resolved_model = resolve(task)
        kwargs.setdefault("model", resolved_model)
        kwargs.setdefault("max_output_tokens", max_tokens_for_task(task))
        provider = self.provider_for(task)
        return await provider.create_response(**kwargs)

    def response_stream(self, task: str, **kwargs):
        """Response stream.

    Args:
        task: (str) Tham số `task`.
        kwargs: (Any) Tham số `kwargs`."""
        _, resolved_model = resolve(task)
        kwargs.setdefault("model", resolved_model)
        kwargs.setdefault("max_output_tokens", max_tokens_for_task(task))
        provider = self.provider_for(task)
        return provider.response_stream(**kwargs)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed texts (async).

    Args:
        texts: (list[str]) Tham số `texts`.

    Returns:
        (list[list[float]]) Kết quả trả về."""
        provider = self.provider_for(TASK_EMBEDDING)
        return await provider.embed_texts(texts)


_router: LLMRouter | None = None


def get_router() -> LLMRouter:
    """Lấy router.

    Returns:
        (LLMRouter) Kết quả trả về."""
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
