import json
from dataclasses import dataclass, field
from typing import Any, Literal

EventType = Literal["status", "tool_start", "tool_done", "text_delta", "data_preview", "done", "error"]


@dataclass
class AgentEvent:
    type: EventType
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def result(self) -> dict[str, Any] | None:
        return self.data.get("_result")

    def to_sse(self) -> str:
        payload = {"type": self.type, **{k: v for k, v in self.data.items() if not k.startswith("_")}}
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def status(detail_vi: str, detail_en: str) -> AgentEvent:
    return AgentEvent("status", {"detail_vi": detail_vi, "detail_en": detail_en})


def tool_start(tool: str, detail_vi: str, detail_en: str, args) -> AgentEvent:
    return AgentEvent("tool_start", {"tool": tool, "detail_vi": detail_vi, "detail_en": detail_en, "args": args})


def tool_done(tool: str) -> AgentEvent:
    return AgentEvent("tool_done", {"tool": tool})


def text_delta(delta: str) -> AgentEvent:
    return AgentEvent("text_delta", {"delta": delta})


def data_preview(videos: list[dict]) -> AgentEvent:
    return AgentEvent("data_preview", {"videos": videos})


def done(enriched: dict[str, Any]) -> AgentEvent:
    return AgentEvent(
        "done",
        {
            "_result": enriched,
            "data": enriched["data"],
            "tool_calls": enriched["tool_calls"],
        },
    )


def error(message_vi: str, message_en: str) -> AgentEvent:
    return AgentEvent(
        "error",
        {
            "detail_vi": message_vi,
            "detail_en": message_en,
            "message": message_vi,
        },
    )


def error_key(key: str, **params) -> AgentEvent:
    from app.i18n import t

    return AgentEvent(
        "error",
        {
            "detail_vi": t(key, "vi", **params),
            "detail_en": t(key, "en", **params),
            "message": t(key, "vi", **params),
            "message_key": key,
            "message_params": params,
        },
    )
