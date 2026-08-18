from contextlib import asynccontextmanager
from typing import Any, TypeVar
from collections.abc import AsyncIterator

from pydantic import BaseModel

from app.ai.router import TASK_DEFAULT, get_router
from app.ai.types import LLMResponse
from app.config.logger import Logger

T = TypeVar("T", bound=BaseModel)

logger = Logger.get(__name__)


def extract_response_text(response: Any) -> str:
    """Extract the concatenated output text from an LLM response object.

    Prefers the response's `output_text` shortcut when available;
    otherwise concatenates the text of all "output_text" content blocks
    across "message" items in `response.output`.

    Args:
        response: An `LLMResponse` (or duck-typed equivalent) returned by the router.

    Returns:
        The concatenated output text, or an empty string if none is found.
    """
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
    """Check whether a response was marked incomplete for a specific reason.

    Args:
        reason: The incomplete-details reason to match (e.g. "max_output_tokens").
        response: The LLM response object to inspect.

    Returns:
        True if `response.status == "incomplete"` and its
        `incomplete_details.reason` equals `reason`.
    """
    return (
        getattr(response, "status", None) == "incomplete"
        and getattr(response, "incomplete_details", None) is not None
        and (getattr(response.incomplete_details, "reason", None) == reason)
    )


def status_error(response: Any) -> str | None:
    """Build an error message if a response's status indicates failure or cancellation.

    Args:
        response: The LLM response object to inspect.

    Returns:
        A message like "LLM response failed: ..." if status is "failed" or
        "cancelled", otherwise None.
    """
    status = getattr(response, "status", None)
    if status in ("failed", "cancelled"):
        return f"LLM response {status}: {getattr(response, 'error', None)}"
    return None


def output_item_to_input(item: Any) -> dict:
    """Convert a single response output item into the input-item shape for the next turn.

    Used to feed a prior turn's output (function calls, messages, or other
    item types) back into the LLM as conversation input.

    Args:
        item: An output item from an LLM response (e.g. function_call or message).

    Returns:
        A plain dict shaped for "function_call" or "message" items; for
        any other item type, the model-dumped dict with "id", "status",
        and "parsed_arguments" keys stripped.
    """
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
    """Convert a list of response output items into input-item shape via `output_item_to_input`.

    Args:
        output: List of output items from an LLM response.

    Returns:
        The converted list of input-item dicts.
    """
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
    """Create an LLM response via the task-routed model, passing through only the given kwargs.

    Args:
        task: Task key used to select the model/config from the router.
        model: Optional model override.
        instructions: Optional system/developer instructions.
        input: Conversation input (string or list of input items).
        max_output_tokens: Optional cap on output tokens.
        tools: Optional list of tool schemas to make available to the model.
        tool_choice: Optional tool-choice directive ("auto", "none", or a specific tool).

    Returns:
        The raw response object from the underlying router/client.
    """
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
    """Open a streaming LLM response as an async context manager, delegating to the router.

    Args:
        task: Task key used to select the model/config from the router.
        **kwargs: Additional arguments forwarded to the router's `response_stream`.

    Yields:
        The streaming response object from the underlying router/client.
    """
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
    """Run a simple prompt-completion call through the task-routed model.

    Args:
        user_prompt: The user-facing prompt text.
        system_prompt: The system/instruction prompt text.
        max_tokens: Optional cap on output tokens.
        model: Optional model override.
        task: Task key used to select the model/config from the router.

    Returns:
        The completion text returned by the router.
    """
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
    """Run a prompt-completion call through the task-routed model, requesting a JSON-formatted reply.

    Args:
        user_prompt: The user-facing prompt text.
        system_prompt: The system/instruction prompt text.
        max_tokens: Optional cap on output tokens.
        model: Optional model override.
        task: Task key used to select the model/config from the router.

    Returns:
        The raw JSON text returned by the router (not yet parsed).
    """
    return await get_router().complete_json(
        task,
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        model=model,
    )


async def complete_structured(
    user_prompt: str,
    system_prompt: str,
    response_model: type[T],
    max_tokens: int | None = None,
    model: str | None = None,
    *,
    task: str = TASK_DEFAULT,
    max_retries: int = 2,
) -> T:
    """Run a prompt-completion call through the task-routed model, validated
    against `response_model`.

    Args:
        user_prompt: The user-facing prompt text.
        system_prompt: The system/instruction prompt text.
        response_model: Pydantic model the response must validate against.
        max_tokens: Optional cap on output tokens.
        model: Optional model override.
        task: Task key used to select the model/config from the router.
        max_retries: How many times to re-prompt on validation failure.

    Returns:
        A validated `response_model` instance.
    """
    return await get_router().complete_structured(
        task,
        response_model=response_model,
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        model=model,
        max_retries=max_retries,
    )
