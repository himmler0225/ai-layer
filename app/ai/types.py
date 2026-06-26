"""Kiểu response thống nhất giữa OpenAI Responses và Chat Completions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class OutputTextContent:
    type: str = "output_text"
    text: str = ""


@dataclass
class MessageOutputItem:
    type: str = "message"
    role: str = "assistant"
    content: List[OutputTextContent] = field(default_factory=list)


@dataclass
class FunctionCallItem:
    type: str = "function_call"
    call_id: str = ""
    name: str = ""
    arguments: str = "{}"


@dataclass
class IncompleteDetails:
    reason: str = ""


@dataclass
class LLMResponse:
    status: str = "completed"
    output: List[Any] = field(default_factory=list)
    output_text: str = ""
    incomplete_details: Optional[IncompleteDetails] = None
    error: Any = None

    def model_dump(self) -> dict:
        return {
            "status": self.status,
            "output": self.output,
            "output_text": self.output_text,
        }


@dataclass
class StreamTextDelta:
    type: str = "response.output_text.delta"
    delta: str = ""
