from typing import Any

from app.exceptions import AiLayerConfigError, AiLayerLLMError, AiLayerTimeoutError
from app.services.agent.iterate import run_agent_events


def _raise_from_error_event(data: dict[str, Any]) -> None:
    vi = data.get("detail_vi") or data.get("message", "")
    en = data.get("detail_en") or vi
    key = data.get("message_key")
    params = data.get("message_params") or {}
    if key == "errors.agent_max_iterations":
        raise AiLayerTimeoutError(vi, message_key=key, message_params=params, message_en=en)
    raise AiLayerLLMError(vi, message_en=en, message_key=key, message_params=params if key else None)


async def run_agent(task: str, tools: list[dict], max_iter: int = 10, system: str | None = None) -> dict[str, Any]:
    """Chạy agent sync — consume events, trả về kết quả enriched."""
    try:
        async for event in run_agent_events(task, tools, max_iter, system, stream_llm=False):
            if event.type == "error":
                _raise_from_error_event(event.data)
            if event.type == "done" and event.result is not None:
                return event.result
    except AiLayerConfigError:
        raise
    except ValueError as exc:
        raise AiLayerConfigError(str(exc), cause=exc) from exc
    raise AiLayerTimeoutError(
        f"Agent không hoàn tất trong {max_iter} vòng",
        message_key="errors.agent_max_iterations",
        message_params={"max_iter": max_iter},
    )
