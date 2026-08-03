from typing import Any, Literal

from app.config.logger import Logger
from app.services.agent.guards import should_force_synthesis
from app.services.agent.guards.fallback import catalog_forced_tool_choice

logger = Logger.get(__name__)

ToolRoundAction = Literal["continue", "force_synthesis"]


def tool_round_action(ctx: dict[str, Any], iteration: int) -> ToolRoundAction:
    """Sau khi tool round hoàn tất — có nên ép synthesis không."""
    if should_force_synthesis(ctx["tool_call_log"], iteration, ctx["max_iter"]):
        return "force_synthesis"
    return "continue"


def should_retry_empty_tool_round(
    ctx: dict, *, iteration: int, call_items: list, collected_text: str
) -> bool:
    """LLM không gọi tool và không có text ở vòng đầu — có nên ép retry không."""
    if iteration != 1 or ctx["tool_call_log"]:
        return False
    if call_items or collected_text.strip():
        return False
    return bool(ctx["tools"])


def resolve_empty_tool_round(
    ctx: dict,
    *,
    iteration: int,
    attempt: int,
    call_items: list,
    collected_text: str,
    tool_choice: Any,
) -> Any:
    """Return next tool_choice for retry, or None to stop retrying."""
    if not should_retry_empty_tool_round(
        ctx, iteration=iteration, call_items=call_items, collected_text=collected_text
    ):
        return None
    if attempt >= 2:
        return None
    if attempt == 0:
        forced = catalog_forced_tool_choice(ctx["task"], ctx["tools"])
        if forced:
            logger.warning(
                "[agent] empty tool round iter=1, retrying forced tool=%s",
                forced.get("function", {}).get("name"),
            )
            return forced
    logger.warning(
        "[agent] empty tool round iter=1, retrying tool_choice=required tools=%d",
        len(ctx["tools"]),
    )
    return "required"
