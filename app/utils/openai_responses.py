from __future__ import annotations

from typing import Any, Dict, List, Optional

import app.config.settings as _cfg
from app.config.logger import Logger
from app.utils.openai_client import get_openai_client

logger = Logger.get(__name__)


def extract_response_text(response: Any) -> str:
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
    return (
        getattr(response, "status", None) == "incomplete"
        and getattr(response, "incomplete_details", None) is not None
        and getattr(response.incomplete_details, "reason", None) == reason
    )


def status_error(response: Any) -> Optional[str]:
    status = getattr(response, "status", None)
    if status in ("failed", "cancelled"):
        return f"OpenAI response {status}: {getattr(response, 'error', None)}"
    return None


def output_item_to_input(item: Any) -> Dict:
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

    logger.info("[openai] responses.create model=%s", resolved_model)
    return await get_openai_client().responses.create(**kwargs)


async def complete(
    user_prompt: str,
    system_prompt: str,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
) -> str:
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
    system_with_json = (
        f"{system_prompt}\n\nRespond with valid JSON only. No markdown, no explanation."
    )
    return await complete(user_prompt, system_with_json, max_tokens, model)
