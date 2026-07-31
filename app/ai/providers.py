import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from collections.abc import AsyncIterator, Callable

from openai import AsyncOpenAI

import app.config.settings as settings
from app.config.constants import HTTP_MAX_ATTEMPTS
from app.ai.adapters import (
    ChatCompletionStreamAdapter,
    chat_completion_to_llm_response,
    responses_input_to_chat_messages,
    responses_tools_to_chat,
)
from app.ai.base import BaseLLM
from app.config.logger import Logger
from app.exceptions import AiLayerConfigError, AiLayerValidationError
from app.utils.llm_errors import log_error, should_retry
from app.utils.retry import retry_delay

logger = Logger.get(__name__)

_clients: dict[str, AsyncOpenAI] = {}


@dataclass(frozen=True)
class ProviderSpec:
    """Lớp `ProviderSpec` (kế thừa object)."""

    name: str
    settings_prefix: str
    base_url: str | None = None
    fallback_model: str = ""
    supports_embeddings: bool = False


from app.config.loader import provider_settings_prefix

_ALIASES = {"deep_seek": "deepseek"}


def normalize_provider(name: str) -> str:
    """Chuẩn hóa provider.

    Args:
        name: (str) Tham số `name`.

    Returns:
        (str) Kết quả trả về."""
    key = (name or "").strip().lower()
    return _ALIASES.get(key, key)


def get_provider_spec(name: str) -> ProviderSpec:
    """Lấy provider spec từ settings (Supabase AI_MODELS)."""
    key = normalize_provider(name)
    prefix = provider_settings_prefix(key)
    embedding_provider = normalize_provider(getattr(settings, "LLM_EMBEDDING_PROVIDER", "") or "")
    return ProviderSpec(
        name=key,
        settings_prefix=prefix,
        supports_embeddings=bool(embedding_provider) and key == embedding_provider,
    )


def _setting(spec: ProviderSpec, field: str, default: Any = None) -> Any:
    """(Nội bộ) Setting `_setting`.

    Args:
        spec: (ProviderSpec) Tham số `spec`.
        field: (str) Tham số `field`.
        default: (Any, mặc định None) Tham số `default`.

    Returns:
        (Any) Kết quả trả về."""
    value = getattr(settings, f"{spec.settings_prefix}_{field}", None)
    return value if value not in (None, "", 0) else default


def get_sdk_client(spec: ProviderSpec) -> AsyncOpenAI:
    """Lấy sdk client.

    Args:
        spec: (ProviderSpec) Tham số `spec`.

    Returns:
        (AsyncOpenAI) Kết quả trả về."""
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


def reset_clients() -> None:
    """Reset clients.

    Returns:
        (None) Kết quả trả về."""
    _clients.clear()


async def _with_retry(fn: Callable[[], Any], *, where: str) -> Any:
    """(Nội bộ) With retry (async).

    Args:
        fn: (Callable[[], Any]) Tham số `fn`.
        where: (str) Tham số `where`.

    Returns:
        (Any) Kết quả trả về."""
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
    """Lớp `ConfiguredLLM` (kế thừa BaseLLM)."""

    def __init__(self, spec: ProviderSpec):
        """Khởi tạo instance.

        Args:
            spec: (ProviderSpec) Tham số `spec`."""
        self._spec = spec
        self.name = spec.name

    def default_model(self) -> str:
        """Default model.

        Returns:
            (str) Kết quả trả về."""
        return _setting(self._spec, "MODEL") or ""

    def tool_model(self) -> str:
        """Tool model.

        Returns:
            (str) Kết quả trả về."""
        return _setting(self._spec, "TOOL_MODEL") or self.default_model()

    def default_max_tokens(self) -> int:
        """Default max tokens.

        Returns:
            (int) Kết quả trả về."""
        return _setting(self._spec, "TOOL_MAX_TOKENS") or _setting(self._spec, "MAX_TOKENS") or 4096

    def _client(self) -> AsyncOpenAI:
        """(Nội bộ) Client `_client`.

        Returns:
            (AsyncOpenAI) Kết quả trả về."""
        return get_sdk_client(self._spec)

    async def complete(
        self,
        *,
        user_prompt: str,
        system_prompt: str = "",
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Hoàn tất `complete` (async).

        Args:
            user_prompt: (str) Tham số `user_prompt`.
            system_prompt: (str, mặc định '') Tham số `system_prompt`.
            model: (Optional[str], mặc định None) Tham số `model`.
            max_tokens: (Optional[int], mặc định None) Tham số `max_tokens`.

        Returns:
            (str) Kết quả trả về."""
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
        """Hoàn tất json (async).

        Args:
            user_prompt: (str) Tham số `user_prompt`.
            system_prompt: (str, mặc định '') Tham số `system_prompt`.
            model: (Optional[str], mặc định None) Tham số `model`.
            max_tokens: (Optional[int], mặc định None) Tham số `max_tokens`.

        Returns:
            (str) Kết quả trả về."""
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
        """Tạo response (async).

        Args:
            model: (Optional[str], mặc định None) Tham số `model`.
            instructions: (Optional[str], mặc định None) Tham số `instructions`.
            input: (Any, mặc định None) Tham số `input`.
            max_output_tokens: (Optional[int], mặc định None) Tham số `max_output_tokens`.
            tools: (Optional[List[Dict]], mặc định None) Tham số `tools`.
            tool_choice: (Optional[str], mặc định None) Tham số `tool_choice`.

        Returns:
            (Any) Kết quả trả về."""
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
        """(Nội bộ) Tạo response chat (async).

        Args:
            model: (Optional[str]) Tham số `model`.
            instructions: (Optional[str]) Tham số `instructions`.
            input: (Any) Tham số `input`.
            max_output_tokens: (Optional[int]) Tham số `max_output_tokens`.
            tools: (Optional[List[Dict]]) Tham số `tools`.
            tool_choice: (Optional[str]) Tham số `tool_choice`.

        Returns:
            (Any) Kết quả trả về."""
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
            "[llm:%s] chat.completions model=%s tools=%s",
            self.name,
            resolved_model,
            len(chat_tools),
        )

        async def _call() -> Any:
            """(Nội bộ) Call `_call` (async).

            Returns:
                (Any) Kết quả trả về."""
            completion = await self._client().chat.completions.create(**kwargs)
            return chat_completion_to_llm_response(completion)

        return await _with_retry(_call, where=f"{self.name}.chat.completions")

    @asynccontextmanager
    async def response_stream(self, **kwargs: Any) -> AsyncIterator[Any]:
        """Response stream (async).

        Args:
            kwargs: (Any) Tham số `kwargs`.

        Returns:
            (AsyncIterator[Any]) Kết quả trả về."""
        async with self._response_stream_chat(**kwargs) as stream:
            yield stream

    @asynccontextmanager
    async def _response_stream_chat(self, **kwargs: Any) -> AsyncIterator[Any]:
        """(Nội bộ) Response stream chat (async).

        Args:
            kwargs: (Any) Tham số `kwargs`.

        Returns:
            (AsyncIterator[Any]) Kết quả trả về."""
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
            """(Nội bộ) Open `_open` (async).

            Returns:
                (Any) Kết quả trả về."""
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
        """Embed texts (async).

        Args:
            texts: (List[str]) Tham số `texts`.
            model: (Optional[str], mặc định None) Tham số `model`.
            dimensions: (Optional[int], mặc định None) Tham số `dimensions`.

        Returns:
            (List[List[float]]) Kết quả trả về."""
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
