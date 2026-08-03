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
        """Result.

        Returns:
            (dict[str, Any] | None) Kết quả trả về."""
        return self.data.get("_result")

    def to_sse(self) -> str:
        """To sse.

        Returns:
            (str) Kết quả trả về."""
        payload = {"type": self.type, **{k: v for k, v in self.data.items() if not k.startswith("_")}}
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def status(detail_vi: str, detail_en: str) -> AgentEvent:
    """Status.

    Args:
        detail_vi: (str) Tham số `detail_vi`.
        detail_en: (str) Tham số `detail_en`.

    Returns:
        (AgentEvent) Kết quả trả về."""
    return AgentEvent("status", {"detail_vi": detail_vi, "detail_en": detail_en})


def tool_start(tool: str, detail_vi: str, detail_en: str, args, worker: str | None = None) -> AgentEvent:
    """Tool start.

    Args:
        tool: (str) Tham số `tool`.
        detail_vi: (str) Tham số `detail_vi`.
        detail_en: (str) Tham số `detail_en`.
        args: (Any) Tham số `args`.
        worker: (str | None) Domain worker phát sinh event này (multi-agent).

    Returns:
        (AgentEvent) Kết quả trả về."""
    data = {"tool": tool, "detail_vi": detail_vi, "detail_en": detail_en, "args": args}
    if worker:
        data["worker"] = worker
    return AgentEvent("tool_start", data)


def tool_done(tool: str, worker: str | None = None) -> AgentEvent:
    """Tool done.

    Args:
        tool: (str) Tham số `tool`.
        worker: (str | None) Domain worker phát sinh event này (multi-agent).

    Returns:
        (AgentEvent) Kết quả trả về."""
    data = {"tool": tool}
    if worker:
        data["worker"] = worker
    return AgentEvent("tool_done", data)


def text_delta(delta: str) -> AgentEvent:
    """Text delta.

    Args:
        delta: (str) Tham số `delta`.

    Returns:
        (AgentEvent) Kết quả trả về."""
    return AgentEvent("text_delta", {"delta": delta})


def data_preview(videos: list[dict], worker: str | None = None) -> AgentEvent:
    """Data preview.

    Args:
        videos: (list[dict]) Tham số `videos`.
        worker: (str | None) Domain worker phát sinh event này (multi-agent).

    Returns:
        (AgentEvent) Kết quả trả về."""
    data = {"videos": videos}
    if worker:
        data["worker"] = worker
    return AgentEvent("data_preview", data)


def done(enriched: dict[str, Any]) -> AgentEvent:
    """Done.

    Args:
        enriched: (dict[str, Any]) Tham số `enriched`.

    Returns:
        (AgentEvent) Kết quả trả về."""
    return AgentEvent(
        "done",
        {
            "_result": enriched,
            "data": enriched["data"],
            "tool_calls": enriched["tool_calls"],
        },
    )


def error(message_vi: str, message_en: str) -> AgentEvent:
    """Error.

    Args:
        message_vi: (str) Tham số `message_vi`.
        message_en: (str) Tham số `message_en`.

    Returns:
        (AgentEvent) Kết quả trả về."""
    return AgentEvent(
        "error",
        {
            "detail_vi": message_vi,
            "detail_en": message_en,
            "message": message_vi,
        },
    )


def error_key(key: str, **params) -> AgentEvent:
    """Error key.

    Args:
        key: (str) Tham số `key`.
        **params: (Any) Tham số `**params`.

    Returns:
        (AgentEvent) Kết quả trả về."""
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
