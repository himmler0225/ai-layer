from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from openai import AsyncOpenAI

import app.config.settings as settings
from app.ai.adapters import (
    ChatCompletionStreamAdapter,
    chat_completion_to_llm_response,
    responses_input_to_chat_messages,
    responses_tools_to_chat,
)
from app.ai.base import BaseLLM
from app.config.logger import Logger
from app.utils.llm_errors import log_error, should_retry

logger = Logger.get(__name__)

_clients: Dict[str, AsyncOpenAI] = {}


@dataclass(frozen=True)
class ProviderSpec:
    """    Lớp `ProviderSpec` (kế thừa object)."""
    name: str
    settings_prefix: str
    base_url: str | None = None
    fallback_model: str = ""
    use_responses_api: bool = False
    supports_embeddings: bool = False


PROVIDER_SPECS: Dict[str, ProviderSpec] = {
    # Tạm tắt — hết token / gateway không ổn định.
    # "openai": ProviderSpec(
    #     name="openai",
    #     settings_prefix="OPENAI",
    #     fallback_model="gpt-4o",
    #     use_responses_api=True,
    #     supports_embeddings=True,
    # ),
    "deepseek": ProviderSpec(
        name="deepseek",
        settings_prefix="DEEP_SEEK",
        base_url="https://api.deepseek.com",
        fallback_model="deepseek-chat",
    ),
    # "xah": ProviderSpec(
    #     name="xah",
    #     settings_prefix="XAH",
    #     base_url="https://api.xah.io/v1",
    #     fallback_model="deepseek-chat",
    # ),
}

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
    """Lấy provider spec.

    Args:
        name: (str) Tham số `name`.

    Returns:
        (ProviderSpec) Kết quả trả về."""
    key = normalize_provider(name)
    spec = PROVIDER_SPECS.get(key)
    if spec is None:
        raise ValueError(f"LLM provider not found: {name}")
    return spec


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
            raise RuntimeError(f"{spec.settings_prefix}_API_KEY is not configured")
        kwargs: Dict[str, Any] = {"api_key": api_key}
        if spec.base_url:
            kwargs["base_url"] = spec.base_url
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
    for attempt in (1, 2):
        try:
            return await fn()
        except Exception as exc:
            last_exc = exc
            log_error(logger, exc, where=f"{where} attempt={attempt}")
            if attempt == 1 and should_retry(exc):
                await asyncio.sleep(2)
                continue
            raise
    raise last_exc


class ConfiguredLLM(BaseLLM):
    """    Lớp `ConfiguredLLM` (kế thừa BaseLLM)."""
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
        return _setting(self._spec, "MODEL", self._spec.fallback_model)

    def tool_model(self) -> str:
        """Tool model.

    Returns:
        (str) Kết quả trả về."""
        return _setting(self._spec, "TOOL_MODEL") or self.default_model()

    def default_max_tokens(self) -> int:
        """Default max tokens.

    Returns:
        (int) Kết quả trả về."""
        return (
            _setting(self._spec, "TOOL_MAX_TOKENS")
            or _setting(self._spec, "MAX_TOKENS")
            or 4096
        )

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
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Hoàn tất `complete` (async).

    Args:
        user_prompt: (str) Tham số `user_prompt`.
        system_prompt: (str, mặc định '') Tham số `system_prompt`.
        model: (Optional[str], mặc định None) Tham số `model`.
        max_tokens: (Optional[int], mặc định None) Tham số `max_tokens`.

    Returns:
        (str) Kết quả trả về."""
        messages: List[Dict[str, str]] = []
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
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
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
        model: Optional[str] = None,
        instructions: Optional[str] = None,
        input: Any = None,
        max_output_tokens: Optional[int] = None,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
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
        if self._spec.use_responses_api:
            return await self._create_response_native(
                model=model,
                instructions=instructions,
                input=input,
                max_output_tokens=max_output_tokens,
                tools=tools,
                tool_choice=tool_choice,
            )
        return await self._create_response_chat(
            model=model,
            instructions=instructions,
            input=input,
            max_output_tokens=max_output_tokens,
            tools=tools,
            tool_choice=tool_choice,
        )

    async def _create_response_native(
        self,
        *,
        model: Optional[str],
        instructions: Optional[str],
        input: Any,
        max_output_tokens: Optional[int],
        tools: Optional[List[Dict]],
        tool_choice: Optional[str],
    ) -> Any:
        """(Nội bộ) Tạo response native (async).

    Args:
        model: (Optional[str]) Tham số `model`.
        instructions: (Optional[str]) Tham số `instructions`.
        input: (Any) Tham số `input`.
        max_output_tokens: (Optional[int]) Tham số `max_output_tokens`.
        tools: (Optional[List[Dict]]) Tham số `tools`.
        tool_choice: (Optional[str]) Tham số `tool_choice`.

    Returns:
        (Any) Kết quả trả về."""
        resolved_model = model or self.default_model()
        kwargs: Dict[str, Any] = {
            "model": resolved_model,
            "max_output_tokens": max_output_tokens or self.default_max_tokens(),
        }
        if instructions is not None:
            kwargs["instructions"] = instructions
        if input is not None:
            kwargs["input"] = input
        if tools is not None:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        logger.info(
            "[llm:%s] responses.create model=%s tools=%s",
            self.name,
            resolved_model,
            len(tools or []),
        )

        async def _call() -> Any:
            """(Nội bộ) Call `_call` (async).

    Returns:
        (Any) Kết quả trả về."""
            return await self._client().responses.create(**kwargs)

        return await _with_retry(_call, where=f"{self.name}.responses.create")

    async def _create_response_chat(
        self,
        *,
        model: Optional[str],
        instructions: Optional[str],
        input: Any,
        max_output_tokens: Optional[int],
        tools: Optional[List[Dict]],
        tool_choice: Optional[str],
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
        kwargs: Dict[str, Any] = {
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
        if self._spec.use_responses_api:
            async with self._response_stream_native(**kwargs) as stream:
                yield stream
            return
        async with self._response_stream_chat(**kwargs) as stream:
            yield stream

    @asynccontextmanager
    async def _response_stream_native(self, **kwargs: Any) -> AsyncIterator[Any]:
        """(Nội bộ) Response stream native (async).

    Args:
        kwargs: (Any) Tham số `kwargs`.

    Returns:
        (AsyncIterator[Any]) Kết quả trả về."""
        last_exc: Exception | None = None
        for attempt in (1, 2):
            try:
                async with self._client().responses.stream(**kwargs) as stream:
                    yield stream
                    return
            except Exception as exc:
                last_exc = exc
                log_error(logger, exc, where=f"{self.name}.responses.stream attempt={attempt}")
                if attempt == 1 and should_retry(exc):
                    await asyncio.sleep(2)
                    continue
                raise
        raise last_exc

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
        req: Dict[str, Any] = {
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
        for attempt in (1, 2):
            try:
                stream = await _open()
                adapter = ChatCompletionStreamAdapter(stream)
                async with adapter:
                    yield adapter
                return
            except Exception as exc:
                last_exc = exc
                log_error(logger, exc, where=f"{self.name}.stream attempt={attempt}")
                if attempt == 1 and should_retry(exc):
                    await asyncio.sleep(2)
                    continue
                raise
        raise last_exc

    async def embed_texts(
        self,
        texts: List[str],
        *,
        model: Optional[str] = None,
        dimensions: Optional[int] = None,
    ) -> List[List[float]]:
        """Embed texts (async).

    Args:
        texts: (List[str]) Tham số `texts`.
        model: (Optional[str], mặc định None) Tham số `model`.
        dimensions: (Optional[int], mặc định None) Tham số `dimensions`.

    Returns:
        (List[List[float]]) Kết quả trả về."""
        if not self._spec.supports_embeddings:
            raise RuntimeError(
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
