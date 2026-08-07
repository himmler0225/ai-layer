from typing import Any

import app.config.settings as settings
from app.ai.base import BaseLLM
from app.ai.factory import LLMFactory
from app.ai.providers import get_provider_spec, normalize_provider
from app.config.loader import runtime
from app.exceptions import AiLayerConfigError

TASK_AGENT_TOOL = "agent_tool"
TASK_AGENT_SYNTH = "agent_synth"
TASK_ASPECT_GROUP = "aspect_group"
TASK_ASPECT_SUMMARY = "aspect_summary"
TASK_REVIEW_SUMMARY = "review_summary"
TASK_EMBEDDING = "embedding"
TASK_DEFAULT = "default"

TASK_ROUTES: dict[str, tuple[str | None, str | None]] = {
    TASK_AGENT_TOOL: (None, None),
    TASK_AGENT_SYNTH: (None, None),
    TASK_ASPECT_GROUP: (None, None),
    TASK_ASPECT_SUMMARY: (None, None),
    TASK_REVIEW_SUMMARY: (None, None),
    TASK_EMBEDDING: (None, None),
    TASK_DEFAULT: (None, None),
}


def _resolve_provider(task: str) -> str:
    """Resolve which provider to use for a task, based on AI_MODELS.is_active
    (with an embedding-provider override for embedding tasks)."""
    if task == TASK_EMBEDDING:
        emb = (settings.LLM_EMBEDDING_PROVIDER or "").strip()
        if emb:
            return normalize_provider(emb)
    active = (runtime.active_provider or "").strip()
    if not active:
        raise AiLayerConfigError("AI_MODELS: chưa chọn provider is_active — cấu hình trên Supabase / admin")
    return normalize_provider(active)


def _setting(prefix: str, field: str, default: Any = None) -> Any:
    """Read a `{prefix}_{field}` setting, falling back to `default` when it's
    unset, empty string, or `0`.

    Args:
        prefix: Provider settings key prefix.
        field: Setting name suffix (e.g. `"MODEL"`, `"TOOL_MAX_TOKENS"`).
        default: Value to return when the setting is missing/falsy.

    Returns:
        The setting's value, or `default`."""
    value = getattr(settings, f"{prefix}_{field}", None)
    return value if value not in (None, "", 0) else default


def resolve(task: str) -> tuple[str, str]:
    """Resolve which provider and model to use for a given task.

    Args:
        task: One of the `TASK_*` constants (e.g. `TASK_AGENT_TOOL`).

    Returns:
        A `(provider, model)` tuple. `model` comes from `TASK_ROUTES`'
        override if set, otherwise from `_model_for_task`."""
    _, model_override = TASK_ROUTES.get(task, TASK_ROUTES[TASK_DEFAULT])
    provider = _resolve_provider(task)
    model = model_override or _model_for_task(task, provider)
    return (provider, model)


def _model_for_task(task: str, provider: str) -> str:
    """Pick the model name for a task/provider combination.

    Args:
        task: One of the `TASK_*` constants.
        provider: Normalized provider key.

    Returns:
        The tool model for tool-calling/aspect tasks (falling back to the
        default model), or the plain default model for other tasks."""
    spec = get_provider_spec(provider)
    tool_model = _setting(spec.settings_prefix, "TOOL_MODEL")
    model = _setting(spec.settings_prefix, "MODEL") or ""
    if task == TASK_AGENT_TOOL:
        return tool_model or model
    if task == TASK_AGENT_SYNTH:
        return model
    if task in (TASK_ASPECT_GROUP, TASK_ASPECT_SUMMARY):
        return tool_model or model
    return model


def max_tokens_for_task(task: str) -> int:
    """Resolve the max output tokens allowed for a task's resolved provider.

    Args:
        task: One of the `TASK_*` constants.

    Returns:
        The tool max-tokens setting for tool/aspect tasks (falling back to
        the general max-tokens setting, then `4096`); otherwise the general
        max-tokens setting (falling back to `4096`)."""
    provider, _ = resolve(task)
    spec = get_provider_spec(provider)
    tool_max = _setting(spec.settings_prefix, "TOOL_MAX_TOKENS")
    max_tokens = _setting(spec.settings_prefix, "MAX_TOKENS")
    if task in (TASK_AGENT_TOOL, TASK_ASPECT_GROUP, TASK_ASPECT_SUMMARY):
        return tool_max or max_tokens or 4096
    return max_tokens or 4096


class LLMRouter:
    """Routes AI task calls to the configured provider/model, resolving both
    via `resolve()`/`max_tokens_for_task()` before delegating to `LLMFactory`."""

    def provider_for(self, task: str) -> BaseLLM:
        """Get the `BaseLLM` instance for the provider assigned to a task.

        Args:
            task: One of the `TASK_*` constants.

        Returns:
            The (cached) `BaseLLM` instance for the resolved provider."""
        provider_name, _ = resolve(task)
        return LLMFactory.get(provider_name)

    async def complete(
        self,
        task: str,
        *,
        user_prompt: str,
        system_prompt: str = "",
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> str:
        """Run a text completion for `task`, resolving provider/model/limits.

        Args:
            task: One of the `TASK_*` constants.
            user_prompt: The user's message content.
            system_prompt: Optional system instructions.
            max_tokens: Override for the task's resolved max tokens.
            model: Override for the task's resolved model.

        Returns:
            The generated text."""
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
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> str:
        """Run a JSON-constrained completion for `task`, resolving provider/model/limits.

        Args:
            task: One of the `TASK_*` constants.
            user_prompt: The user's message content.
            system_prompt: Optional system instructions.
            max_tokens: Override for the task's resolved max tokens.
            model: Override for the task's resolved model.

        Returns:
            The generated text, expected to be a JSON string."""
        _, resolved_model = resolve(task)
        provider = self.provider_for(task)
        return await provider.complete_json(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            model=model or resolved_model,
            max_tokens=max_tokens or max_tokens_for_task(task),
        )

    async def create_response(self, task: str, **kwargs):
        """Run a Responses-API-style request for `task`, filling in the
        resolved model and max output tokens as defaults.

        Args:
            task: One of the `TASK_*` constants.
            kwargs: Forwarded to `BaseLLM.create_response` (instructions,
                input, tools, tool_choice, etc.); `model` and
                `max_output_tokens` default from the task if not given.

        Returns:
            The provider's response object."""
        _, resolved_model = resolve(task)
        kwargs.setdefault("model", resolved_model)
        kwargs.setdefault("max_output_tokens", max_tokens_for_task(task))
        provider = self.provider_for(task)
        return await provider.create_response(**kwargs)

    def response_stream(self, task: str, **kwargs):
        """Open a streaming Responses-API-style request for `task`, filling in
        the resolved model and max output tokens as defaults.

        Args:
            task: One of the `TASK_*` constants.
            kwargs: Forwarded to `BaseLLM.response_stream`; `model` and
                `max_output_tokens` default from the task if not given.

        Returns:
            The provider's async-context stream object."""
        _, resolved_model = resolve(task)
        kwargs.setdefault("model", resolved_model)
        kwargs.setdefault("max_output_tokens", max_tokens_for_task(task))
        provider = self.provider_for(task)
        return provider.response_stream(**kwargs)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors using the configured embedding provider.

        Args:
            texts: Texts to embed.

        Returns:
            One embedding vector per input text, ordered to match `texts`."""
        provider = self.provider_for(TASK_EMBEDDING)
        return await provider.embed_texts(texts)


_router: LLMRouter | None = None


def get_router() -> LLMRouter:
    """Get the process-wide `LLMRouter` singleton, creating it on first use.

    Returns:
        The shared `LLMRouter` instance."""
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
