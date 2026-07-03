from typing import Any

from app.exceptions import AiLayerConfigError, AiLayerLLMError, AiLayerTimeoutError
from app.services.agent.iterate import run_agent_events


async def run_agent(task: str, tools: list[dict], max_iter: int = 10, system: str | None = None) -> dict[str, Any]:
    """Chạy agent sync — consume events, trả về kết quả enriched."""
    try:
        async for event in run_agent_events(task, tools, max_iter, system, stream_llm=False):
            if event.type == "error":
                msg = event.data.get("message", "")
                if "did not finish within" in msg:
                    raise AiLayerTimeoutError(msg)
                raise AiLayerLLMError(msg)
            if event.type == "done" and event.result is not None:
                return event.result
    except AiLayerConfigError:
        raise
    except ValueError as exc:
        raise AiLayerConfigError(str(exc), cause=exc) from exc
    raise AiLayerTimeoutError(f"Agent did not finish within {max_iter} iterations")
