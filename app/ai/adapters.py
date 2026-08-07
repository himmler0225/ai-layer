import uuid
from typing import Any
from app.ai.types import (
    FunctionCallItem,
    IncompleteDetails,
    LLMResponse,
    MessageOutputItem,
    OutputTextContent,
    StreamTextDelta,
)


def responses_tools_to_chat(tools: list[dict] | None) -> list[dict]:
    """Convert Responses-API tool definitions into Chat Completions tool format.

    Args:
        tools: Tool specs in Responses-API shape (each with a `type` and, for
            function tools, `name`/`description`/`parameters`). May be `None`.

    Returns:
        A list of Chat Completions `{"type": "function", "function": {...}}`
        entries. Non-function tools are dropped; returns `[]` if `tools` is
        falsy."""
    if not tools:
        return []
    out: list[dict] = []
    for tool in tools:
        if tool.get("type") != "function":
            continue
        out.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters") or {"type": "object", "properties": {}},
                },
            }
        )
    return out


def _append_user_message(messages: list[dict], content: str) -> None:
    """Append a user message, merging into the previous one if it was also a user turn.

    Args:
        messages: Chat message list being built, mutated in place.
        content: Text to add as a user message.

    Returns:
        None."""
    if messages and messages[-1].get("role") == "user" and isinstance(messages[-1].get("content"), str):
        messages[-1]["content"] = f"{messages[-1]['content']}\n{content}"
    else:
        messages.append({"role": "user", "content": content})


def responses_input_to_chat_messages(input_items: Any, *, instructions: str | None = None) -> list[dict]:
    """Convert Responses-API input items into Chat Completions messages.

    Handles `instructions` (mapped to a system message), plain user turns,
    `function_call`/`function_call_output` items (mapped to assistant
    `tool_calls` and `tool` role messages respectively), and `message` items
    containing `output_text` blocks. Both dict-shaped items and objects with
    `role`/`content` attributes are accepted.

    Args:
        input_items: A single input item or list of items, in Responses-API
            shape (dicts or objects).
        instructions: Optional system prompt prepended as the first message.

    Returns:
        The resulting list of Chat Completions message dicts."""
    messages: list[dict] = []
    if instructions:
        messages.append({"role": "system", "content": instructions})
    items = input_items if isinstance(input_items, list) else [input_items]
    pending_tool_calls: list[dict] = []
    pending_call_ids: list[str] = []

    def flush_assistant_tool_calls() -> None:
        """Emit the accumulated `function_call` items as one assistant tool_calls message.

        Returns:
            None. No-op if there are no pending tool calls."""
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
                pending_tool_calls.append(
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {"name": item.get("name", ""), "arguments": item.get("arguments") or "{}"},
                    }
                )
                pending_call_ids.append(call_id)
                continue
            if item_type == "function_call_output":
                flush_assistant_tool_calls()
                messages.append(
                    {"role": "tool", "tool_call_id": item.get("call_id", ""), "content": str(item.get("output", ""))}
                )
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
    """Convert an OpenAI ChatCompletion object into the internal LLMResponse shape.

    Extracts tool calls (as `FunctionCallItem`s) if present, otherwise the
    assistant's text content (as a `MessageOutputItem`). Maps a `length`
    finish reason to an `incomplete` status with `max_output_tokens` reason.

    Args:
        completion: The `ChatCompletion` object returned by the OpenAI SDK.

    Returns:
        An `LLMResponse` with `status`, `output`, `output_text`, and
        `incomplete_details` populated."""
    choice = completion.choices[0]
    message = choice.message
    output: list[Any] = []
    text = (message.content or "").strip()
    if message.tool_calls:
        for call in message.tool_calls:
            output.append(
                FunctionCallItem(call_id=call.id, name=call.function.name, arguments=call.function.arguments or "{}")
            )
    elif text:
        output.append(MessageOutputItem(role="assistant", content=[OutputTextContent(text=text)]))
    status = "completed"
    incomplete = None
    finish = getattr(choice, "finish_reason", None)
    if finish == "length":
        status = "incomplete"
        incomplete = IncompleteDetails(reason="max_output_tokens")
    return LLMResponse(status=status, output=output, output_text=text, incomplete_details=incomplete)


class ChatCompletionStreamAdapter:
    """Wraps an OpenAI Chat Completions stream to expose it as an async context
    manager that yields Responses-API-style stream events and can build a
    final `LLMResponse` once the stream is exhausted."""

    def __init__(self, stream: Any):
        """Store the underlying chunk stream and initialize accumulator state.

        Args:
            stream: The async iterable of Chat Completions stream chunks."""
        self._stream = stream
        self._final: LLMResponse | None = None
        self._text = ""
        self._tool_calls: dict[int, dict[str, str]] = {}
        self._finish_reason: str | None = None

    async def __aenter__(self) -> ChatCompletionStreamAdapter:
        """Enter the async context manager.

        Returns:
            This adapter instance."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Close the underlying stream, if it exposes a `close()` method.

        Args:
            args: Exception info passed by the `async with` protocol (unused).

        Returns:
            None."""
        close = getattr(self._stream, "close", None)
        if close:
            await close()

    def __aiter__(self):
        """Return the async iterator of stream events for this adapter."""
        return self._event_iter()

    async def _event_iter(self):
        """Iterate the underlying chunks, yielding text deltas and accumulating
        tool-call fragments and the finish reason, then build the final response."""
        async for chunk in self._stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta
            if delta and delta.content:
                self._text += delta.content
                yield StreamTextDelta(delta=delta.content)
            if delta and delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index if tc.index is not None else 0
                    slot = self._tool_calls.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function and tc.function.name:
                        slot["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        slot["arguments"] += tc.function.arguments
            message = getattr(choice, "message", None)
            if message and getattr(message, "tool_calls", None):
                for idx, tc in enumerate(message.tool_calls):
                    slot = self._tool_calls.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function and tc.function.name:
                        slot["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        slot["arguments"] = tc.function.arguments
            if choice.finish_reason:
                self._finish_reason = choice.finish_reason
        self._build_final()

    def _build_final(self) -> None:
        """Build and cache the final `LLMResponse` from accumulated stream state.

        Prefers accumulated tool calls over accumulated text; maps a `length`
        finish reason to an incomplete status. Idempotent once `_final` is set.

        Returns:
            None."""
        if self._final is not None:
            return
        output: list[Any] = []
        if self._tool_calls:
            for idx in sorted(self._tool_calls):
                slot = self._tool_calls[idx]
                output.append(
                    FunctionCallItem(
                        call_id=slot["id"] or f"call_{uuid.uuid4().hex[:12]}",
                        name=slot["name"],
                        arguments=slot["arguments"] or "{}",
                    )
                )
        elif self._text:
            output.append(MessageOutputItem(content=[OutputTextContent(text=self._text)]))
        status = "completed"
        incomplete = None
        if self._finish_reason == "length":
            status = "incomplete"
            incomplete = IncompleteDetails(reason="max_output_tokens")
        self._final = LLMResponse(status=status, output=output, output_text=self._text, incomplete_details=incomplete)

    async def get_final_response(self) -> LLMResponse:
        """Return the final `LLMResponse`, building it first if the stream hasn't
        been fully consumed yet.

        Returns:
            The accumulated `LLMResponse`."""
        if self._final is None:
            self._build_final()
        return self._final
