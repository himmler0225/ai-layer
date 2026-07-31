from contextlib import asynccontextmanager
from typing import Any
from collections.abc import AsyncIterator

from app.ai.router import TASK_DEFAULT, get_router
from app.ai.types import LLMResponse
from app.config.logger import Logger

logger = Logger.get(__name__)


def extract_response_text(response: Any) -> str:
    """Trích xuất response text.

    Args:
        response: (Any) Tham số `response`.

    Returns:
        (str) Kết quả trả về."""
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
    """Is incomplete for.

    Args:
        reason: (str) Tham số `reason`.
        response: (Any) Tham số `response`.

    Returns:
        (bool) Kết quả trả về."""
    return (
        getattr(response, "status", None) == "incomplete"
        and getattr(response, "incomplete_details", None) is not None
        and (getattr(response.incomplete_details, "reason", None) == reason)
    )


def status_error(response: Any) -> str | None:
    """Status error.

    Args:
        response: (Any) Tham số `response`.

    Returns:
        (str | None) Kết quả trả về."""
    status = getattr(response, "status", None)
    if status in ("failed", "cancelled"):
        return f"LLM response {status}: {getattr(response, 'error', None)}"
    return None


def output_item_to_input(item: Any) -> dict:
    """Output item to input.

    Args:
        item: (Any) Tham số `item`.

    Returns:
        (dict) Kết quả trả về."""
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


def output_items_to_input(output: list[Any]) -> list[dict]:
    """Output items to input.

    Args:
        output: (list[Any]) Tham số `output`.

    Returns:
        (list[dict]) Kết quả trả về."""
    return [output_item_to_input(item) for item in output]


async def create_response(
    *,
    task: str = TASK_DEFAULT,
    model: str | None = None,
    instructions: str | None = None,
    input: Any = None,
    max_output_tokens: int | None = None,
    tools: list[dict] | None = None,
    tool_choice: str | dict[str, Any] | None = None,
) -> Any:
    """Tạo response (async).

    Args:
        task: (str, mặc định TASK_DEFAULT) Tham số `task`.
        model: (str | None, mặc định None) Tham số `model`.
        instructions: (str | None, mặc định None) Tham số `instructions`.
        input: (Any, mặc định None) Tham số `input`.
        max_output_tokens: (int | None, mặc định None) Tham số `max_output_tokens`.
        tools: (list[dict] | None, mặc định None) Tham số `tools`.
        tool_choice: (str | dict[str, Any] | None, mặc định None) Tham số `tool_choice`.

    Returns:
        (Any) Kết quả trả về."""
    kwargs: dict[str, Any] = {}
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
async def response_stream(*, task: str = TASK_DEFAULT, **kwargs: Any) -> AsyncIterator[Any]:
    """Response stream (async).

    Args:
        task: (str, mặc định TASK_DEFAULT) Tham số `task`.
        **kwargs: (Any) Tham số `**kwargs`.

    Returns:
        (AsyncIterator[Any]) Kết quả trả về."""
    async with get_router().response_stream(task, **kwargs) as stream:
        yield stream


async def complete(
    user_prompt: str,
    system_prompt: str,
    max_tokens: int | None = None,
    model: str | None = None,
    *,
    task: str = TASK_DEFAULT,
) -> str:
    """Hoàn tất (async).

    Args:
        user_prompt: (str) Tham số `user_prompt`.
        system_prompt: (str) Tham số `system_prompt`.
        max_tokens: (int | None, mặc định None) Tham số `max_tokens`.
        model: (str | None, mặc định None) Tham số `model`.
        task: (str, mặc định TASK_DEFAULT) Tham số `task`.

    Returns:
        (str) Kết quả trả về."""
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
    max_tokens: int | None = None,
    model: str | None = None,
    *,
    task: str = TASK_DEFAULT,
) -> str:
    """Hoàn tất json (async).

    Args:
        user_prompt: (str) Tham số `user_prompt`.
        system_prompt: (str) Tham số `system_prompt`.
        max_tokens: (int | None, mặc định None) Tham số `max_tokens`.
        model: (str | None, mặc định None) Tham số `model`.
        task: (str, mặc định TASK_DEFAULT) Tham số `task`.

    Returns:
        (str) Kết quả trả về."""
    return await get_router().complete_json(
        task,
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        model=model,
    )
