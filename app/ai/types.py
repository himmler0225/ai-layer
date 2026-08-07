from dataclasses import dataclass, field
from typing import Any


@dataclass
class OutputTextContent:
    """A single text content block within a Responses-API message output item."""

    type: str = "output_text"
    text: str = ""


@dataclass
class MessageOutputItem:
    """A Responses-API output item representing an assistant/user message,
    holding one or more text content blocks."""

    type: str = "message"
    role: str = "assistant"
    content: list[OutputTextContent] = field(default_factory=list)


@dataclass
class FunctionCallItem:
    """A Responses-API output item representing a single tool/function call
    requested by the model, with its call id, function name, and JSON
    arguments string."""

    type: str = "function_call"
    call_id: str = ""
    name: str = ""
    arguments: str = "{}"


@dataclass
class IncompleteDetails:
    """Explains why an `LLMResponse` is incomplete (e.g. truncated output)."""

    reason: str = ""


@dataclass
class LLMResponse:
    """Normalized result of an LLM call, mirroring the shape of the OpenAI
    Responses API regardless of which underlying provider/API produced it."""

    status: str = "completed"
    output: list[Any] = field(default_factory=list)
    output_text: str = ""
    incomplete_details: IncompleteDetails | None = None
    error: Any = None

    def model_dump(self) -> dict:
        """Serialize the response to a plain dict for JSON responses.

        Returns:
            A dict with `status`, `output`, and `output_text` keys (omits
            `incomplete_details` and `error`)."""
        return {"status": self.status, "output": self.output, "output_text": self.output_text}


@dataclass
class StreamTextDelta:
    """A single incremental text chunk emitted while streaming an LLM response."""

    type: str = "response.output_text.delta"
    delta: str = ""
