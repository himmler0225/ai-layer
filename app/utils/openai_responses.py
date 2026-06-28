"""Gọi LLM qua Router — giữ API cũ cho agent/ingest."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional

from app.ai.router import TASK_DEFAULT, get_router
from app.ai.types import LLMResponse
from app.config.logger import Logger

logger = Logger.get(__name__)


def extract_response_text(response: Any) -> str:
    """Lấy toàn bộ text từ response OpenAI hoặc LLMResponse."""
    if isinstance(response, LLMResponse):
        if response.output_text:
            return response.output_text
        chunks: list[str] = []
        for item in response.output:
            if getattr(item, "type", None) == "message":
                for content in item.content:
                    if getattr(content, "type", None) == "output_text":
                        chunks.append(content.text)
        return "".join(chunks)

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
        return f"LLM response {status}: {getattr(response, 'error', None)}"
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
    task: str = TASK_DEFAULT,
    model: Optional[str] = None,
    instructions: Optional[str] = None,
    input: Any = None,
    max_output_tokens: Optional[int] = None,
    tools: Optional[List[Dict]] = None,
    tool_choice: Optional[str] = None,
) -> Any:
    """Gọi LLM Responses/Chat (có tools) — provider do router chọn."""
    kwargs: Dict[str, Any] = {}
    if model is not None:
        kwargs["model"] = model
    if instructions is not None:
        kwargs["instructions"] = instructions
    if input is not None:
        kwargs["input"] = input
    if max_output_tokens is not None:
        kwargs["max_output_tokens"] = max_output_tokens
    if tools is not None:
        kwargs["tools"] = tools
    if tool_choice is not None:
        kwargs["tool_choice"] = tool_choice

    return await get_router().create_response(task, **kwargs)


@asynccontextmanager
async def response_stream_with_retry(
    *, task: str = TASK_DEFAULT, **kwargs: Any
) -> AsyncIterator[Any]:
    """LLM stream — retry một lần khi 429/5xx/timeout (trong provider)."""
    async with get_router().response_stream(task, **kwargs) as stream:
        yield stream


async def complete(
    user_prompt: str,
    system_prompt: str,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
    *,
    task: str = TASK_DEFAULT,
) -> str:
    """Gọi LLM trả text thuần (không tools)."""
    return await get_router().complete(
        task,
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        model=model,
    )


async def complete_json(
    user_prompt: str,
    system_prompt: str,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
    *,
    task: str = TASK_DEFAULT,
) -> str:
    """Gọi LLM và yêu cầu trả JSON."""
    return await get_router().complete_json(
        task,
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        model=model,
    )
