from __future__ import annotations
from typing import Any, Dict, List, Optional
from app.ai.router import TASK_AGENT_TOOL
from app.config.logger import Logger
from app.services.agent import config
from app.services.agent.engine import process_agent_step
from app.services.agent.loop import bootstrap_agent, finish_agent, handle_incomplete_sync
from app.services.agent.synthesis import run_synthesis
from app.exceptions import AiLayerConfigError, AiLayerLLMError, AiLayerTimeoutError
from app.utils.llm_errors import log_error, user_message
from app.utils.llm_responses import create_response, status_error
logger = Logger.get(__name__)

async def run_agent(task: str, tools: List[Dict], max_iter: int=10, system: Optional[str]=None) -> Dict[str, Any]:
    """Chạy agent (async).

    Args:
        task: (str) Tham số `task`.
        tools: (List[Dict]) Tham số `tools`.
        max_iter: (int, mặc định 10) Tham số `max_iter`.
        system: (Optional[str], mặc định None) Tham số `system`.

    Returns:
        (Dict[str, Any]) Kết quả trả về."""
    try:
        ctx = await bootstrap_agent(task, tools, system, max_iter)
    except AiLayerConfigError:
        raise
    except ValueError as exc:
        raise AiLayerConfigError(str(exc), cause=exc) from exc
    for iteration in range(1, ctx['max_iter'] + 1):
        logger.info('[agent] iteration=%d/%d model=%s', iteration, ctx['max_iter'], config.tool_model())
        try:
            response = await create_response(task=TASK_AGENT_TOOL, model=config.tool_model(), max_output_tokens=config.tool_max_tokens(), instructions=ctx['system'], tools=ctx['tools'], tool_choice='auto', input=ctx['input_items'])
        except Exception as exc:
            log_error(logger, exc, where=f'agent iter={iteration}')
            raise AiLayerLLMError(user_message(exc), cause=exc) from exc
        err = status_error(response)
        if err:
            raise AiLayerLLMError(err)
        outcome = await process_agent_step(ctx, response, iteration)
        if outcome.action == 'incomplete':
            return await handle_incomplete_sync(ctx, response, iteration)
        if outcome.action == 'continue':
            continue
        if outcome.action == 'force_synthesis':
            final_text = await run_synthesis(
                system=ctx['system'],
                task=ctx['task'],
                tool_call_log=ctx['tool_call_log'],
            )
            return await finish_agent(ctx, iteration=iteration, final_text=final_text)
        if outcome.action == 'complete':
            return await finish_agent(ctx, iteration=iteration, final_text=outcome.final_text)
    if ctx['tool_call_log']:
        final_text = await run_synthesis(
            system=ctx['system'],
            task=ctx['task'],
            tool_call_log=ctx['tool_call_log'],
        )
        return await finish_agent(ctx, iteration=iteration, final_text=final_text)
    raise AiLayerTimeoutError(f"Agent did not finish within {ctx['max_iter']} iterations")
