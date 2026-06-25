"""Gọi OpenAI Responses API."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional

import app.config.settings as _cfg
from app.config.logger import Logger
from app.utils.openai_client import get_openai_client
from app.utils.openai_errors import log_error, should_retry

logger = Logger.get(__name__)


def extract_response_text(response: Any) -> str:
    """Lấy toàn bộ text từ response OpenAI."""
    text = getattr(response, "output_text", None)
    if text is not None:
        return text

    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) == "message":
            for content in item.content:
                if getattr(content, "type", None) == "output_text":
                    chunks.append(content.text)
    return "".join(chunks)


def is_incomplete_for(reason: str, response: Any) -> bool:
    """Kiểm tra response bị cắt vì hết token."""
    return (
        getattr(response, "status", None) == "incomplete"
        and getattr(response, "incomplete_details", None) is not None
        and getattr(response.incomplete_details, "reason", None) == reason
    )


def status_error(response: Any) -> Optional[str]:
    """Trả message lỗi nếu response failed/cancelled."""
    status = getattr(response, "status", None)
    if status in ("failed", "cancelled"):
        return f"OpenAI response {status}: {getattr(response, 'error', None)}"
    return None


def output_item_to_input(item: Any) -> Dict:
    """Chuyển một output item sang input cho vòng tiếp theo."""
    item_type = getattr(item, "type", None)

    if item_type == "function_call":
        return {
            "type": "function_call",
            "call_id": item.call_id,
            "name": item.name,
            "arguments": item.arguments,
        }

    if item_type == "message":
        return {
            "type": "message",
            "role": getattr(item, "role", "assistant"),
            "content": [
                {"type": "output_text", "text": content.text}
                for content in item.content
                if getattr(content, "type", None) == "output_text"
            ],
        }

    dumped = item.model_dump() if hasattr(item, "model_dump") else dict(item)
    for key in ("id", "status", "parsed_arguments"):
        dumped.pop(key, None)
    return dumped


def output_items_to_input(output: List[Any]) -> List[Dict]:
    """Chuyển toàn bộ output sang input messages."""
    return [output_item_to_input(item) for item in output]


async def create_response(
    *,
    model: Optional[str] = None,
    instructions: Optional[str] = None,
    input: Any = None,
    max_output_tokens: Optional[int] = None,
    tools: Optional[List[Dict]] = None,
    tool_choice: Optional[str] = None,
) -> Any:
    """Gọi OpenAI Responses API (có tools)."""
    resolved_model = model or _cfg.OPENAI_MODEL
    kwargs: Dict[str, Any] = {
        "model": resolved_model,
        "max_output_tokens": max_output_tokens or _cfg.OPENAI_MAX_TOKENS,
    }

    if instructions is not None:
        kwargs["instructions"] = instructions
    if input is not None:
        kwargs["input"] = input
    if tools is not None:
        kwargs["tools"] = tools
    if tool_choice is not None:
        kwargs["tool_choice"] = tool_choice

    logger.info("[openai] responses.create model=%s tools=%s", resolved_model, len(tools or []))

    last_exc: Exception | None = None
    for attempt in (1, 2):
        try:
            return await get_openai_client().responses.create(**kwargs)
        except Exception as exc:
            last_exc = exc
            log_error(logger, exc, where=f"responses.create attempt={attempt}")
            if attempt == 1 and should_retry(exc):
                await asyncio.sleep(2)
                continue
            raise
    raise last_exc  # type: ignore[misc]


@asynccontextmanager
async def response_stream_with_retry(**kwargs: Any) -> AsyncIterator[Any]:
    """OpenAI Responses stream — retry một lần khi 429/5xx/timeout."""
    last_exc: Exception | None = None
    for attempt in (1, 2):
        try:
            async with get_openai_client().responses.stream(**kwargs) as stream:
                yield stream
                return
        except Exception as exc:
            last_exc = exc
            log_error(logger, exc, where=f"responses.stream attempt={attempt}")
            if attempt == 1 and should_retry(exc):
                await asyncio.sleep(2)
                continue
            raise
    raise last_exc  # type: ignore[misc]


async def complete(
    user_prompt: str,
    system_prompt: str,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
) -> str:
    """Gọi LLM trả text thuần (không tools)."""
    inputs: List[Dict[str, str]] = []
    if system_prompt:
        inputs.append({"role": "system", "content": system_prompt})
    inputs.append({"role": "user", "content": user_prompt})

    response = await create_response(
        model=model,
        input=inputs,
        max_output_tokens=max_tokens,
    )
    return extract_response_text(response)


async def complete_json(
    user_prompt: str,
    system_prompt: str,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
) -> str:
    """Gọi LLM và yêu cầu trả JSON."""
    system_with_json = (
        f"{system_prompt}\n\nRespond with valid JSON only. No markdown, no explanation."
    )
    return await complete(user_prompt, system_with_json, max_tokens, model)