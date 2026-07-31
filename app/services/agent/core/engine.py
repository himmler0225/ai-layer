from dataclasses import dataclass, field
from typing import Any, Literal

from app.services.agent.guards import should_force_synthesis
from app.services.agent.core.context import (
    begin_tool_round,
    complete_tool_round,
    is_max_tokens_incomplete,
    resolve_final_text,
)

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
