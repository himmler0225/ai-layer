import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, TypeVar
from collections.abc import AsyncIterator, Callable

import instructor
from openai import AsyncOpenAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

import app.config.settings as settings
from app.config.constants import HTTP_MAX_ATTEMPTS
from app.ai.adapters import (
    ChatCompletionStreamAdapter,
    chat_completion_to_llm_response,
    responses_input_to_chat_messages,
    responses_tools_to_chat,
)
from app.ai.base import BaseLLM
from app.config.logger import Logger, log_event
from app.exceptions import AiLayerConfigError, AiLayerValidationError
from app.utils.llm_errors import log_error, should_retry
from app.utils.retry import retry_delay

logger = Logger.get(__name__)

_clients: dict[str, AsyncOpenAI] = {}
_instructor_clients: dict[str, instructor.AsyncInstructor] = {}


@dataclass(frozen=True)
class ProviderSpec:
    """Static description of an LLM provider: its settings key prefix, base
    URL, fallback model, and whether it supports embeddings."""

    name: str
    settings_prefix: str
    base_url: str | None = None
    fallback_model: str = ""
    supports_embeddings: bool = False


from app.config.loader import provider_settings_prefix

_ALIASES = {"deep_seek": "deepseek"}


def normalize_provider(name: str) -> str:
    """Normalize a provider name: trim, lowercase, and resolve known aliases.

    Args:
        name: Raw provider name (e.g. from settings or user input).

    Returns:
        The canonical lowercase provider key (e.g. `"deep_seek"` -> `"deepseek"`)."""
    key = (name or "").strip().lower()
    return _ALIASES.get(key, key)


def get_provider_spec(name: str) -> ProviderSpec:
    """Build a `ProviderSpec` for a provider from settings (backed by Supabase AI_MODELS)."""
    key = normalize_provider(name)
    prefix = provider_settings_prefix(key)
    embedding_provider = normalize_provider(getattr(settings, "LLM_EMBEDDING_PROVIDER", "") or "")
    return ProviderSpec(
        name=key,
        settings_prefix=prefix,
        supports_embeddings=bool(embedding_provider) and key == embedding_provider,
    )


def _setting(spec: ProviderSpec, field: str, default: Any = None) -> Any:
    """Read a `{settings_prefix}_{field}` setting, falling back to `default`
    when it's unset, empty string, or `0`.

    Args:
        spec: Provider spec supplying the settings key prefix.
        field: Setting name suffix (e.g. `"API_KEY"`, `"MODEL"`).
        default: Value to return when the setting is missing/falsy.

    Returns:
        The setting's value, or `default`."""
    value = getattr(settings, f"{spec.settings_prefix}_{field}", None)
    return value if value not in (None, "", 0) else default


def get_sdk_client(spec: ProviderSpec) -> AsyncOpenAI:
    """Get or lazily create the cached `AsyncOpenAI` client for a provider.

    Args:
        spec: Provider spec identifying which client/config to use.

    Returns:
        The cached `AsyncOpenAI` client instance for this provider.

    Raises:
        AiLayerConfigError: If the provider's API key or base URL is not
            configured."""
    if spec.name not in _clients:
        api_key = _setting(spec, "API_KEY")
        if not api_key:
            raise AiLayerConfigError(f"{spec.settings_prefix}_API_KEY is not configured")
        base_url = _setting(spec, "BASE_URL")
        if not base_url:
            raise AiLayerConfigError(f"{spec.settings_prefix}_BASE_URL is not configured")
        kwargs: dict[str, Any] = {"api_key": api_key, "base_url": base_url}
        _clients[spec.name] = AsyncOpenAI(**kwargs)
    return _clients[spec.name]


def get_instructor_client(spec: ProviderSpec) -> instructor.AsyncInstructor:
    """Get or lazily create the cached `instructor`-wrapped client for a provider.

    Wraps the same cached `AsyncOpenAI` instance `get_sdk_client()` returns, so
    it shares that client's connection pool/auth/base_url.

    Args:
        spec: Provider spec identifying which client/config to use.

    Returns:
        The cached `instructor.AsyncInstructor` client for this provider."""
    if spec.name not in _instructor_clients:
        _instructor_clients[spec.name] = instructor.from_openai(get_sdk_client(spec))
    return _instructor_clients[spec.name]


def reset_clients() -> None:
    """Clear the cached SDK clients, forcing them to be recreated on next use.

    Returns:
        None."""
    _clients.clear()
    _instructor_clients.clear()


async def _with_retry(fn: Callable[[], Any], *, where: str) -> Any:
    """Call `fn`, retrying on retryable exceptions with backoff delay.

    Args:
        fn: Zero-argument async callable to invoke.
        where: Label used in retry/error log messages (e.g. provider/method).

    Returns:
        The result of `fn()`.

    Raises:
        Exception: The last exception encountered, once retries (up to
            `HTTP_MAX_ATTEMPTS`) are exhausted or the error isn't retryable."""
    last_exc: Exception | None = None
    for attempt in range(1, HTTP_MAX_ATTEMPTS + 1):
        try:
            return await fn()
        except Exception as exc:
            last_exc = exc
            log_error(logger, exc, where=f"{where} attempt={attempt}")
            if attempt < HTTP_MAX_ATTEMPTS and should_retry(exc):
                await asyncio.sleep(retry_delay(attempt))
                continue
            raise
    raise last_exc


class ConfiguredLLM(BaseLLM):
    """`BaseLLM` implementation backed by any OpenAI-compatible Chat
    Completions API, configured per-provider via `ProviderSpec`/settings."""

    def __init__(self, spec: ProviderSpec):
        """Store the provider spec and set the instance's provider name.

        Args:
            spec: Provider configuration this instance will use."""
        self._spec = spec
        self.name = spec.name

    def default_model(self) -> str:
        """Return this provider's configured default model name, or `""` if unset.

        Returns:
            The `{prefix}_MODEL` setting value, or an empty string."""
        return _setting(self._spec, "MODEL") or ""

    def tool_model(self) -> str:
        """Return the model to use for tool/function-calling requests.

        Returns:
            The `{prefix}_TOOL_MODEL` setting if configured, otherwise
            `default_model()`."""
        return _setting(self._spec, "TOOL_MODEL") or self.default_model()

    def default_max_tokens(self) -> int:
        """Return the default max output tokens for this provider.

        Returns:
            `{prefix}_TOOL_MAX_TOKENS`, then `{prefix}_MAX_TOKENS`, then `4096`
            as a final fallback."""
        return _setting(self._spec, "TOOL_MAX_TOKENS") or _setting(self._spec, "MAX_TOKENS") or 4096

    def _client(self) -> AsyncOpenAI:
        """Get the cached `AsyncOpenAI` client for this provider.

        Returns:
            The provider's `AsyncOpenAI` client instance."""
        return get_sdk_client(self._spec)

    async def complete(
        self,
        *,
        user_prompt: str,
        system_prompt: str = "",
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Run a single-turn chat completion via the provider's SDK client.

        Args:
            user_prompt: The user's message content.
            system_prompt: Optional system instructions; omitted if empty.
            model: Model override; falls back to `default_model()`.
            max_tokens: Max output tokens; falls back to `default_max_tokens()`.

        Returns:
            The assistant's reply text, stripped of surrounding whitespace."""
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        response = await self._client().chat.completions.create(
            model=model or self.default_model(),
            messages=messages,
            max_tokens=max_tokens or self.default_max_tokens(),
        )
        return (response.choices[0].message.content or "").strip()

    async def complete_json(
        self,
        *,
        user_prompt: str,
        system_prompt: str = "",
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Run `complete()` with an appended instruction to respond with JSON only.

        Args:
            user_prompt: The user's message content.
            system_prompt: Optional system instructions; the JSON-only
                instruction is appended to it (or used alone if empty).
            model: Model override; falls back to `default_model()`.
            max_tokens: Max output tokens; falls back to `default_max_tokens()`.

        Returns:
            The generated text, expected to be a JSON string."""
        json_system = (
            f"{system_prompt}\n\nRespond with valid JSON only. No markdown, no explanation."
            if system_prompt
            else "Respond with valid JSON only. No markdown, no explanation."
        )
        return await self.complete(
            user_prompt=user_prompt,
            system_prompt=json_system,
            model=model,
            max_tokens=max_tokens,
        )

    async def complete_structured(
        self,
        *,
        response_model: type[T],
        user_prompt: str,
        system_prompt: str = "",
        model: str | None = None,
        max_tokens: int | None = None,
        max_retries: int = 2,
    ) -> T:
        """Run a chat completion validated against `response_model` via `instructor`.

        Args:
            response_model: Pydantic model the response must validate against.
            user_prompt: The user's message content.
            system_prompt: Optional system instructions; omitted if empty.
            model: Model override; falls back to `default_model()`.
            max_tokens: Max output tokens; falls back to `default_max_tokens()`.
            max_retries: How many times `instructor` re-prompts on validation
                failure before raising.

        Returns:
            A validated `response_model` instance."""
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        return await get_instructor_client(self._spec).chat.completions.create(
            response_model=response_model,
            model=model or self.default_model(),
            messages=messages,
            max_tokens=max_tokens or self.default_max_tokens(),
            max_retries=max_retries,
        )

    async def create_response(
        self,
        *,
        model: str | None = None,
        instructions: str | None = None,
        input: Any = None,
        max_output_tokens: int | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> Any:
        """Run a Responses-API-style request, translated to Chat Completions.

        Args:
            model: Model override; falls back to `tool_model()`.
            instructions: Optional system-level instructions.
            input: Responses-API-shaped input items (or plain content).
            max_output_tokens: Max output tokens; falls back to
                `default_max_tokens()`.
            tools: Optional Responses-API-shaped tool definitions.
            tool_choice: Optional tool-choice directive; defaults to `"auto"`
                when tools are present.

        Returns:
            An `LLMResponse` built from the Chat Completions result."""
        return await self._create_response_chat(
            model=model,
            instructions=instructions,
            input=input,
            max_output_tokens=max_output_tokens,
            tools=tools,
            tool_choice=tool_choice,
        )

    async def _create_response_chat(
        self,
        *,
        model: str | None,
        instructions: str | None,
        input: Any,
        max_output_tokens: int | None,
        tools: list[dict] | None,
        tool_choice: str | dict[str, Any] | None,
    ) -> Any:
        """Build and send the Chat Completions request for `create_response`,
        with retry on transient errors.

        Args:
            model: Model override; falls back to `tool_model()`.
            instructions: Optional system-level instructions.
            input: Responses-API-shaped input items.
            max_output_tokens: Max output tokens; falls back to
                `default_max_tokens()`.
            tools: Optional Responses-API-shaped tool definitions.
            tool_choice: Optional tool-choice directive.

        Returns:
            An `LLMResponse` built from the completion result."""
        resolved_model = model or self.tool_model()
        messages = responses_input_to_chat_messages(input, instructions=instructions)
        chat_tools = responses_tools_to_chat(tools)
        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "messages": messages,
            "max_tokens": max_output_tokens or self.default_max_tokens(),
        }
        if chat_tools:
            kwargs["tools"] = chat_tools
            kwargs["tool_choice"] = tool_choice or "auto"
        logger.info(
            log_event(
                "llm",
                "chat completion request",
                provider=self.name,
                model=resolved_model,
                tools=len(chat_tools),
            )
        )

        async def _call() -> Any:
            """Issue the chat completion request and adapt it to an `LLMResponse`.

            Returns:
                The adapted `LLMResponse`."""
            completion = await self._client().chat.completions.create(**kwargs)
            return chat_completion_to_llm_response(completion)

        return await _with_retry(_call, where=f"{self.name}.chat.completions")

    @asynccontextmanager
    async def response_stream(self, **kwargs: Any) -> AsyncIterator[Any]:
        """Async context manager yielding a `ChatCompletionStreamAdapter` for a
        streaming Responses-API-style request.

        Args:
            kwargs: Same parameters as `create_response` (model, instructions,
                input, max_output_tokens, tools, tool_choice).

        Returns:
            An async context yielding the stream adapter."""
        async with self._response_stream_chat(**kwargs) as stream:
            yield stream

    @asynccontextmanager
    async def _response_stream_chat(self, **kwargs: Any) -> AsyncIterator[Any]:
        """Open a streaming Chat Completions request and wrap it in a
        `ChatCompletionStreamAdapter`, retrying on transient errors.

        Args:
            kwargs: model, instructions, input, max_output_tokens, tools,
                tool_choice — same as `create_response`.

        Returns:
            An async context yielding the `ChatCompletionStreamAdapter`."""
        model = kwargs.pop("model", None) or self.tool_model()
        instructions = kwargs.pop("instructions", None)
        input_items = kwargs.pop("input", None)
        max_output_tokens = kwargs.pop("max_output_tokens", None) or self.default_max_tokens()
        tools = kwargs.pop("tools", None)
        tool_choice = kwargs.pop("tool_choice", None)
        messages = responses_input_to_chat_messages(input_items, instructions=instructions)
        chat_tools = responses_tools_to_chat(tools)
        req: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_output_tokens,
            "stream": True,
        }
        if chat_tools:
            req["tools"] = chat_tools
            req["tool_choice"] = tool_choice or "auto"

        async def _open() -> Any:
            """Issue the streaming chat completion request.

            Returns:
                The raw async stream returned by the OpenAI SDK."""
            return await self._client().chat.completions.create(**req)

        last_exc: Exception | None = None
        for attempt in range(1, HTTP_MAX_ATTEMPTS + 1):
            try:
                stream = await _open()
                adapter = ChatCompletionStreamAdapter(stream)
                async with adapter:
                    yield adapter
                return
            except Exception as exc:
                last_exc = exc
                log_error(logger, exc, where=f"{self.name}.stream attempt={attempt}")
                if attempt < HTTP_MAX_ATTEMPTS and should_retry(exc):
                    await asyncio.sleep(retry_delay(attempt))
                    continue
                raise
        raise last_exc

    async def embed_texts(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> list[list[float]]:
        """Generate embedding vectors for a batch of texts via this provider.

        Args:
            texts: Texts to embed; returns `[]` immediately if empty.
            model: Embedding model override; defaults to `settings.EMBEDDING_MODEL`.
            dimensions: Embedding dimensionality override; defaults to
                `settings.EMBEDDING_DIM`.

        Returns:
            One embedding vector per input text, ordered to match `texts`.

        Raises:
            AiLayerValidationError: If this provider is not configured as the
                embedding provider (`supports_embeddings` is `False`)."""
        if not self._spec.supports_embeddings:
            raise AiLayerValidationError(
                f"{self.name} provider does not support embeddings — use task=embedding (openai)"
            )
        if not texts:
            return []
        response = await self._client().embeddings.create(
            model=model or settings.EMBEDDING_MODEL,
            input=texts,
            dimensions=dimensions or settings.EMBEDDING_DIM,
        )
        ordered = sorted(response.data, key=lambda row: row.index)
        return [row.embedding for row in ordered]
