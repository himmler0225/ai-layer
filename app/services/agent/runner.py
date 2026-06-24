from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

import app.services.prompts as _prompts
from app.config.logger import Logger
from app.services.agent import config
from app.services.agent.constants import HISTORY_MARKER
from app.services.agent.finalize import finish
from app.services.agent.platform import filter_tools_by_platform
from app.services.agent.synthesis import run_synthesis
from app.services.agent.tools import execute_parallel, extract_function_calls
from app.utils.openai_responses import (
    create_response,
    extract_response_text,
    is_incomplete_for,
    output_items_to_input,
    status_error,
)

logger = Logger.get(__name__)


async def run_agent(
    task: str,
    tools: List[Dict],
    max_iter: int = 10,
    system: Optional[str] = None,
) -> Dict[str, Any]:
    """Chạy agent đồng bộ — trả dict enrich đầy đủ."""
    system = system or _prompts.AGENT_SYSTEM
    tools = filter_tools_by_platform(tools, task)

    session_id = str(uuid.uuid4())
    input_items: List[Dict] = [{"role": "user", "content": task}]
    tool_call_log: List[Dict] = []
    has_history = HISTORY_MARKER in task

    for iteration in range(1, max_iter + 1):
        logger.info("[agent] iteration=%d/%d model=%s", iteration, max_iter, config.tool_model())

        force_tool = iteration == 1 and not tool_call_log and not has_history
        response = await create_response(
            model=config.tool_model(),
            max_output_tokens=config.tool_max_tokens(),
            instructions=system,
            tools=tools,
            tool_choice="required" if force_tool else "auto",
            input=input_items,
        )

        err = status_error(response)
        if err:
            raise RuntimeError(err)

        if is_incomplete_for("max_output_tokens", response):
            return await _handle_incomplete(
                response, system, input_items, session_id, task, iteration, tool_call_log,
            )

        if extract_function_calls(response.output):
            input_items.extend(output_items_to_input(response.output))
            outputs, entries = await execute_parallel(response.output, session_id, task, iteration)
            tool_call_log.extend(entries)
            input_items.extend(outputs)
            continue

        final_text = await _resolve_final_text(response, system, input_items, tool_call_log)
        return await finish(
            session_id=session_id,
            task=task,
            iteration=iteration,
            tool_call_log=tool_call_log,
            final_text=final_text,
        )

    raise RuntimeError(f"Agent did not finish within {max_iter} iterations")


async def _resolve_final_text(response, system, input_items, tool_call_log) -> str:
    """Lấy câu trả lời cuối — nếu dual-mode thì dùng model tổng hợp riêng."""
    if config.dual_mode() and tool_call_log:
        logger.info("[agent] synthesis model=%s", config.synth_model())
        input_items.extend(output_items_to_input(response.output))
        return await run_synthesis(system=system, input_items=input_items)
    return extract_response_text(response)


async def _handle_incomplete(response, system, input_items, session_id, task, iteration, tool_call_log):
    """Xử lý khi model hết token giữa chừng."""
    if config.dual_mode() and tool_call_log:
        logger.warning("[agent] max_output_tokens iteration=%d mode=dual_synthesis", iteration)
        input_items.extend(output_items_to_input(response.output))
        final_text = await run_synthesis(system=system, input_items=input_items)
        return await finish(
            session_id=session_id, task=task, iteration=iteration,
            tool_call_log=tool_call_log, final_text=final_text,
        )

    partial = extract_response_text(response)
    if partial:
        return await finish(
            session_id=session_id, task=task, iteration=iteration,
            tool_call_log=tool_call_log, final_text=partial,
        )
    raise RuntimeError(f"Model hit max_output_tokens at iteration {iteration} without text.")