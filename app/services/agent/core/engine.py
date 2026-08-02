from dataclasses import dataclass, field
from typing import Any, Literal

from app.config.logger import Logger
from app.services.agent.guards import should_force_synthesis
from app.services.agent.guards.fallback import catalog_forced_tool_choice
from app.services.agent.core.context import (
    begin_tool_round,
    complete_tool_round,
    is_max_tokens_incomplete,
    resolve_final_text,
)

logger = Logger.get(__name__)

Action = Literal["incomplete", "continue", "force_synthesis", "complete"]
ToolRoundAction = Literal["continue", "force_synthesis"]


@dataclass
class AgentStepOutcome:
    """Kết quả một vòng LLM sau khi xử lý tool / synthesis decision."""

    action: Action
    call_items: list[Any] = field(default_factory=list)
    final_text: str = ""
    response: Any = None


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


async def process_agent_step(
    ctx: dict[str, Any],
    response: Any,
    iteration: int,
) -> AgentStepOutcome:
    """Logic chung cho runner sau mỗi LLM response."""
    if is_max_tokens_incomplete(response):
        return AgentStepOutcome(action="incomplete", response=response)

    call_items = await begin_tool_round(ctx, response.output)
    if call_items:
        await complete_tool_round(ctx, response.output, iteration)
        action = tool_round_action(ctx, iteration)
        return AgentStepOutcome(
            action=action,
            call_items=call_items,
            response=response,
        )

    final_text = await resolve_final_text(ctx, response)
    return AgentStepOutcome(
        action="complete",
        final_text=final_text,
        response=response,
    )
