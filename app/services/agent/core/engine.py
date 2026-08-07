from typing import Any, Literal

from app.config.logger import Logger, log_event
from app.services.agent.guards import should_force_synthesis
from app.services.agent.guards.fallback import catalog_forced_tool_choice

logger = Logger.get(__name__)

ToolRoundAction = Literal["continue", "force_synthesis"]


def tool_round_action(ctx: dict[str, Any], iteration: int) -> ToolRoundAction:
    """After a tool round completes, decide whether synthesis should be forced."""
    if should_force_synthesis(ctx["tool_call_log"], iteration, ctx["max_iter"]):
        return "force_synthesis"
    return "continue"


def should_retry_empty_tool_round(
    ctx: dict, *, iteration: int, call_items: list, collected_text: str
) -> bool:
    """Whether to force a retry when the LLM called no tool and returned no text on the first iteration."""
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
                log_event(
                    "agent",
                    "empty tool round retry",
                    iteration=1,
                    strategy="forced_tool",
                    tool=forced.get("function", {}).get("name"),
                )
            )
            return forced
    logger.warning(
        log_event(
            "agent",
            "empty tool round retry",
            iteration=1,
            strategy="tool_choice_required",
            tools=len(ctx["tools"]),
        )
    )
    return "required"
