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


def status(detail: str) -> AgentEvent:
    return AgentEvent("status", {"detail": detail})


def tool_start(tool: str, detail: str, args, worker: str | None = None) -> AgentEvent:
    data = {"tool": tool, "detail": detail, "args": args}
    if worker:
        data["worker"] = worker
    return AgentEvent("tool_start", data)


def tool_done(tool: str, worker: str | None = None) -> AgentEvent:
    data = {"tool": tool}
    if worker:
        data["worker"] = worker
    return AgentEvent("tool_done", data)


def text_delta(delta: str) -> AgentEvent:
    return AgentEvent("text_delta", {"delta": delta})


def data_preview(videos: list[dict], worker: str | None = None) -> AgentEvent:
    data = {"videos": videos}
    if worker:
        data["worker"] = worker
    return AgentEvent("data_preview", data)


def done(enriched: dict[str, Any]) -> AgentEvent:
    return AgentEvent(
        "done",
        {
            "_result": enriched,
            "data": enriched["data"],
            "tool_calls": enriched["tool_calls"],
        },
    )


def error(detail: str) -> AgentEvent:
    return AgentEvent(
        "error",
        {
            "detail": detail,
            "message": detail,
        },
    )


def error_key(key: str, **params) -> AgentEvent:
    from app.i18n import msg

    detail = msg(key, **params)
    return AgentEvent(
        "error",
        {
            "detail": detail,
            "message": detail,
            "message_key": key,
            "message_params": params,
        },
    )
