"""Chuyển đổi schema OpenAI Responses ↔ Chat Completions."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

from app.ai.types import (
    FunctionCallItem,
    IncompleteDetails,
    LLMResponse,
    MessageOutputItem,
    OutputTextContent,
    StreamTextDelta,
)


def responses_tools_to_chat(tools: List[Dict] | None) -> List[Dict]:
    if not tools:
        return []
    out: List[Dict] = []
    for tool in tools:
        if tool.get("type") != "function":
            continue
        out.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters") or {"type": "object", "properties": {}},
            },
        })
    return out


def _append_user_message(messages: List[Dict], content: str) -> None:
    if messages and messages[-1].get("role") == "user" and isinstance(messages[-1].get("content"), str):
        messages[-1]["content"] = f"{messages[-1]['content']}\n{content}"
    else:
        messages.append({"role": "user", "content": content})


def responses_input_to_chat_messages(input_items: Any, *, instructions: str | None = None) -> List[Dict]:
    """Chuyển input Responses API sang messages cho chat.completions."""
    messages: List[Dict] = []
    if instructions:
        messages.append({"role": "system", "content": instructions})

    items = input_items if isinstance(input_items, list) else [input_items]
    pending_tool_calls: List[Dict] = []
    pending_call_ids: List[str] = []

    def flush_assistant_tool_calls() -> None:
        nonlocal pending_tool_calls, pending_call_ids
        if not pending_tool_calls:
            return
        messages.append({"role": "assistant", "tool_calls": pending_tool_calls})
        pending_tool_calls = []
        pending_call_ids = []

    for item in items:
        if isinstance(item, dict):
            item_type = item.get("type")
            role = item.get("role")
            if role == "user" and item.get("content") is not None:
                flush_assistant_tool_calls()
                _append_user_message(messages, str(item["content"]))
                continue
            if item_type == "function_call":
                call_id = item.get("call_id") or f"call_{uuid.uuid4().hex[:12]}"
                pending_tool_calls.append({
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": item.get("name", ""),
                        "arguments": item.get("arguments") or "{}",
                    },
                })
                pending_call_ids.append(call_id)
                continue
            if item_type == "function_call_output":
                flush_assistant_tool_calls()
                messages.append({
                    "role": "tool",
                    "tool_call_id": item.get("call_id", ""),
                    "content": str(item.get("output", "")),
                })
                continue
            if item_type == "message":
                flush_assistant_tool_calls()
                text_parts = []
                for block in item.get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "output_text":
                        text_parts.append(block.get("text", ""))
                if text_parts:
                    messages.append({"role": item.get("role", "assistant"), "content": "".join(text_parts)})
                continue

        role = getattr(item, "role", None)
        content = getattr(item, "content", None)
        if role == "user" and content is not None:
            flush_assistant_tool_calls()
            _append_user_message(messages, str(content))

    flush_assistant_tool_calls()
    return messages


def chat_completion_to_llm_response(completion: Any) -> LLMResponse:
    choice = completion.choices[0]
    message = choice.message
    output: List[Any] = []
    text = (message.content or "").strip()

    if message.tool_calls:
        for call in message.tool_calls:
            output.append(FunctionCallItem(
                call_id=call.id,
                name=call.function.name,
                arguments=call.function.arguments or "{}",
            ))
    elif text:
        output.append(MessageOutputItem(
            role="assistant",
            content=[OutputTextContent(text=text)],
        ))

    status = "completed"
    incomplete = None
    finish = getattr(choice, "finish_reason", None)
    if finish == "length":
        status = "incomplete"
        incomplete = IncompleteDetails(reason="max_output_tokens")

    return LLMResponse(
        status=status,
        output=output,
        output_text=text,
        incomplete_details=incomplete,
    )


class ChatCompletionStreamAdapter:
    """Bọc chat.completions stream → event giống OpenAI Responses stream."""

    def __init__(self, stream: Any):
        self._stream = stream
        self._final: LLMResponse | None = None
        self._text = ""
        self._tool_calls: Dict[int, Dict[str, str]] = {}
        self._finish_reason: str | None = None

    async def __aenter__(self) -> ChatCompletionStreamAdapter:
        return self

    async def __aexit__(self, *args: Any) -> None:
        close = getattr(self._stream, "close", None)
        if close:
            await close()

    def __aiter__(self):
        return self._event_iter()

    async def _event_iter(self):
        async for chunk in self._stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta

            if delta.content:
                self._text += delta.content
                yield StreamTextDelta(delta=delta.content)

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    slot = self._tool_calls.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function and tc.function.name:
                        slot["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        slot["arguments"] += tc.function.arguments

            if choice.finish_reason:
                self._finish_reason = choice.finish_reason

        self._build_final()

    def _build_final(self) -> None:
        if self._final is not None:
            return
        output: List[Any] = []
        if self._tool_calls:
            for idx in sorted(self._tool_calls):
                slot = self._tool_calls[idx]
                output.append(FunctionCallItem(
                    call_id=slot["id"] or f"call_{uuid.uuid4().hex[:12]}",
                    name=slot["name"],
                    arguments=slot["arguments"] or "{}",
                ))
        elif self._text:
            output.append(MessageOutputItem(
                content=[OutputTextContent(text=self._text)],
            ))

        status = "completed"
        incomplete = None
        if self._finish_reason == "length":
            status = "incomplete"
            incomplete = IncompleteDetails(reason="max_output_tokens")

        self._final = LLMResponse(
            status=status,
            output=output,
            output_text=self._text,
            incomplete_details=incomplete,
        )

    async def get_final_response(self) -> LLMResponse:
        if self._final is None:
            self._build_final()
        return self._final  # type: ignore[return-value]
