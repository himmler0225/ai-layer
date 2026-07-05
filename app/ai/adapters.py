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
    """Responses tools to chat.

    Args:
        tools: (List[Dict] | None) Tham số `tools`.

    Returns:
        (List[Dict]) Kết quả trả về."""
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
    """(Nội bộ) Append user message.

    Args:
        messages: (List[Dict]) Tham số `messages`.
        content: (str) Tham số `content`.

    Returns:
        (None) Kết quả trả về."""
    if messages and messages[-1].get("role") == "user" and isinstance(messages[-1].get("content"), str):
        messages[-1]["content"] = f"{messages[-1]['content']}\n{content}"
    else:
        messages.append({"role": "user", "content": content})


def responses_input_to_chat_messages(input_items: Any, *, instructions: str | None = None) -> list[dict]:
    """Responses input to chat messages.

    Args:
        input_items: (Any) Tham số `input_items`.
        instructions: (str | None, mặc định None) Tham số `instructions`.

    Returns:
        (List[Dict]) Kết quả trả về."""
    messages: list[dict] = []
    if instructions:
        messages.append({"role": "system", "content": instructions})
    items = input_items if isinstance(input_items, list) else [input_items]
    pending_tool_calls: list[dict] = []
    pending_call_ids: list[str] = []

    def flush_assistant_tool_calls() -> None:
        """Flush assistant tool calls.

        Returns:
            (None) Kết quả trả về."""
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
    """Chat completion to llm response.

    Args:
        completion: (Any) Tham số `completion`.

    Returns:
        (LLMResponse) Kết quả trả về."""
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
    """Lớp `ChatCompletionStreamAdapter` (kế thừa object)."""

    def __init__(self, stream: Any):
        """Khởi tạo instance.

        Args:
            stream: (Any) Tham số `stream`."""
        self._stream = stream
        self._final: LLMResponse | None = None
        self._text = ""
        self._tool_calls: dict[int, dict[str, str]] = {}
        self._finish_reason: str | None = None

    async def __aenter__(self) -> ChatCompletionStreamAdapter:
        """Vào async context manager (async).

        Returns:
            (ChatCompletionStreamAdapter) Kết quả trả về."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Thoát async context manager (async).

        Args:
            args: (Any) Tham số `args`.

        Returns:
            (None) Kết quả trả về."""
        close = getattr(self._stream, "close", None)
        if close:
            await close()

    def __aiter__(self):
        """Trả về async iterator."""
        return self._event_iter()

    async def _event_iter(self):
        """(Nội bộ) Event iter (async)."""
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
        """(Nội bộ) Xây dựng final.

        Returns:
            (None) Kết quả trả về."""
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
        """Lấy final response (async).

        Returns:
            (LLMResponse) Kết quả trả về."""
        if self._final is None:
            self._build_final()
        return self._final
