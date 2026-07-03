from dataclasses import dataclass, field
from typing import Any


@dataclass
class OutputTextContent:
    """Lớp `OutputTextContent` (kế thừa object)."""

    type: str = "output_text"
    text: str = ""


@dataclass
class MessageOutputItem:
    """Lớp `MessageOutputItem` (kế thừa object)."""

    type: str = "message"
    role: str = "assistant"
    content: list[OutputTextContent] = field(default_factory=list)


@dataclass
class FunctionCallItem:
    """Lớp `FunctionCallItem` (kế thừa object)."""

    type: str = "function_call"
    call_id: str = ""
    name: str = ""
    arguments: str = "{}"


@dataclass
class IncompleteDetails:
    """Lớp `IncompleteDetails` (kế thừa object)."""

    reason: str = ""


@dataclass
class LLMResponse:
    """Lớp `LLMResponse` (kế thừa object)."""

    status: str = "completed"
    output: list[Any] = field(default_factory=list)
    output_text: str = ""
    incomplete_details: IncompleteDetails | None = None
    error: Any = None

    def model_dump(self) -> dict:
        """Model dump.

        Returns:
            (dict) Kết quả trả về."""
        return {"status": self.status, "output": self.output, "output_text": self.output_text}


@dataclass
class StreamTextDelta:
    """Lớp `StreamTextDelta` (kế thừa object)."""

    type: str = "response.output_text.delta"
    delta: str = ""
