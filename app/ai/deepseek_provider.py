"""DeepSeek provider — OpenAI-compatible Chat Completions."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional

from openai import AsyncOpenAI

import app.config.settings as settings
from app.ai.adapters import (ChatCompletionStreamAdapter,
                             chat_completion_to_llm_response,
                             responses_input_to_chat_messages,
                             responses_tools_to_chat)
from app.ai.base import BaseLLM
from app.config.logger import Logger
from app.utils.openai_errors import log_error, should_retry

logger = Logger.get(__name__)

_BASE_URL = "https://api.deepseek.com"
_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if not settings.DEEP_SEEK_API_KEY:
        raise RuntimeError("DEEP_SEEK_API_KEY is not configured")
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.DEEP_SEEK_API_KEY, base_url=_BASE_URL)
    return _client


class DeepSeekProvider(BaseLLM):
    name = "deepseek"

    def default_model(self) -> str:
        return settings.DEEP_SEEK_MODEL or "deepseek-chat"

    def default_max_tokens(self) -> int:
        return settings.OPENAI_TOOL_MAX_TOKENS or settings.OPENAI_MAX_TOKENS or 4096

    async def complete(
        self,
        *,
        user_prompt: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        response = await _get_client().chat.completions.create(
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
        resolved_model = model or settings.DEEP_SEEK_TOOL_MODEL or self.default_model()
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
            "[llm:deepseek] chat.completions model=%s tools=%s",
            resolved_model,
            len(chat_tools),
        )

        last_exc: Exception | None = None
        for attempt in (1, 2):
            try:
                completion = await _get_client().chat.completions.create(**kwargs)
                return chat_completion_to_llm_response(completion)
            except Exception as exc:
                last_exc = exc
                log_error(
                    logger, exc, where=f"deepseek.chat.completions attempt={attempt}"
                )
                if attempt == 1 and should_retry(exc):
                    await asyncio.sleep(2)
                    continue
                raise
        raise last_exc  # type: ignore[misc]

    @asynccontextmanager
    async def response_stream(self, **kwargs: Any) -> AsyncIterator[Any]:
        model = (
            kwargs.pop("model", None)
            or settings.DEEP_SEEK_TOOL_MODEL
            or self.default_model()
        )
        instructions = kwargs.pop("instructions", None)
        input_items = kwargs.pop("input", None)
        max_output_tokens = (
            kwargs.pop("max_output_tokens", None) or self.default_max_tokens()
        )
        tools = kwargs.pop("tools", None)
        tool_choice = kwargs.pop("tool_choice", None)

        messages = responses_input_to_chat_messages(
            input_items, instructions=instructions
        )
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

        last_exc: Exception | None = None
        for attempt in (1, 2):
            try:
                stream = await _get_client().chat.completions.create(**req)
                adapter = ChatCompletionStreamAdapter(stream)
                async with adapter:
                    yield adapter
                return
            except Exception as exc:
                last_exc = exc
                log_error(logger, exc, where=f"deepseek.stream attempt={attempt}")
                if attempt == 1 and should_retry(exc):
                    await asyncio.sleep(2)
                    continue
                raise
        raise last_exc  # type: ignore[misc]

    async def embed_texts(
        self,
        texts: List[str],
        *,
        model: Optional[str] = None,
        dimensions: Optional[int] = None,
    ) -> List[List[float]]:
        raise RuntimeError(
            "DeepSeek provider does not support embeddings — use task=embedding (OpenAI)"
        )
