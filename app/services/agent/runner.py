from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.config.logger import Logger
from app.services.agent import config
from app.services.agent.loop import (
    bootstrap_agent,
    finish_agent,
    handle_incomplete_sync,
    is_max_tokens_incomplete,
    resolve_final_text,
    run_tool_round,
)
from app.utils.openai_errors import log_error, user_message
from app.utils.openai_responses import create_response, status_error
from app.ai.router import TASK_AGENT_TOOL

logger = Logger.get(__name__)


async def run_agent(
    task: str,
    tools: List[Dict],
    max_iter: int = 10,
    system: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        ctx = await bootstrap_agent(task, tools, system, max_iter)
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc

    for iteration in range(1, ctx["max_iter"] + 1):
        logger.info("[agent] iteration=%d/%d model=%s", iteration, ctx["max_iter"], config.tool_model())

        try:
            response = await create_response(
                task=TASK_AGENT_TOOL,
                model=config.tool_model(),
                max_output_tokens=config.tool_max_tokens(),
                instructions=ctx["system"],
                tools=ctx["tools"],
                tool_choice="auto",
                input=ctx["input_items"],
            )
        except Exception as exc:
            log_error(logger, exc, where=f"agent iter={iteration}")
            raise RuntimeError(user_message(exc)) from exc

        err = status_error(response)
        if err:
            raise RuntimeError(err)

        if is_max_tokens_incomplete(response):
            return await handle_incomplete_sync(ctx, response, iteration)

        if await run_tool_round(ctx, response.output, iteration):
            continue

        final_text = await resolve_final_text(ctx, response)
        return await finish_agent(ctx, iteration=iteration, final_text=final_text)

    raise RuntimeError(f"Agent did not finish within {ctx['max_iter']} iterations")
