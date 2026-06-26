"""OpenAI provider — Responses API + embeddings."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional

from openai import AsyncOpenAI

import app.config.settings as _cfg
from app.ai.base import BaseLLM
from app.config.logger import Logger
from app.utils.openai_errors import log_error, should_retry

logger = Logger.get(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if not _cfg.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    if _client is None:
        _client = AsyncOpenAI(api_key=_cfg.OPENAI_API_KEY)
    return _client


class OpenAIProvider(BaseLLM):
    name = "openai"

    def default_model(self) -> str:
        return _cfg.OPENAI_MODEL

    def default_max_tokens(self) -> int:
        return _cfg.OPENAI_MAX_TOKENS or 4096

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

        logger.info("[llm:openai] responses.create model=%s tools=%s", resolved_model, len(tools or []))

        last_exc: Exception | None = None
        for attempt in (1, 2):
            try:
                return await _get_client().responses.create(**kwargs)
            except Exception as exc:
                last_exc = exc
                log_error(logger, exc, where=f"openai.responses.create attempt={attempt}")
                if attempt == 1 and should_retry(exc):
                    await asyncio.sleep(2)
                    continue
                raise
        raise last_exc  # type: ignore[misc]

    @asynccontextmanager
    async def response_stream(self, **kwargs: Any) -> AsyncIterator[Any]:
        last_exc: Exception | None = None
        for attempt in (1, 2):
            try:
                async with _get_client().responses.stream(**kwargs) as stream:
                    yield stream
                    return
            except Exception as exc:
                last_exc = exc
                log_error(logger, exc, where=f"openai.responses.stream attempt={attempt}")
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
        if not texts:
            return []
        response = await _get_client().embeddings.create(
            model=model or _cfg.EMBEDDING_MODEL,
            input=texts,
            dimensions=dimensions or _cfg.EMBEDDING_DIM,
        )
        ordered = sorted(response.data, key=lambda row: row.index)
        return [row.embedding for row in ordered]
