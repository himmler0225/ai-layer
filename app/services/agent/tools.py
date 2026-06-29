from __future__ import annotations
import asyncio
import json
from typing import Any, Dict, List, Tuple
from app.config.logger import Logger
from app.ingest.dispatcher.schedule import schedule_tool_ingest
from app.services.agent.guards import is_search_budget_exhausted, search_budget_message
from app.services.agent.serialize import serialize_result
from app.tools.executor import execute_tool
logger = Logger.get(__name__)

def extract_function_calls(output: List[Any]) -> List[Any]:
    """Trích xuất function calls.

    Args:
        output: (List[Any]) Tham số `output`.

    Returns:
        (List[Any]) Kết quả trả về."""
    return [item for item in output if getattr(item, 'type', None) == 'function_call']

async def execute_parallel(output: List[Any], session_id: str, task: str, iteration: int, *, tool_call_log: List[Dict] | None = None) -> Tuple[List[Dict], List[Dict]]:
    """Thực thi parallel (async).

    Args:
        output: (List[Any]) Tham số `output`.
        session_id: (str) Tham số `session_id`.
        task: (str) Tham số `task`.
        iteration: (int) Tham số `iteration`.

    Returns:
        (Tuple[List[Dict], List[Dict]]) Kết quả trả về."""
    call_items = extract_function_calls(output)
    if not call_items:
        return ([], [])
    logger.info('[agent] executing tools count=%d names=%s', len(call_items), [call.name for call in call_items])

    prior_log = tool_call_log or []

    async def _run(item: Any):
        """(Nội bộ) Chạy `_run` (async).

    Args:
        item: (Any) Tham số `item`."""
        try:
            args = json.loads(item.arguments) if item.arguments else {}
        except json.JSONDecodeError:
            logger.error('[agent] invalid tool args tool=%s raw=%r', item.name, item.arguments)
            args = {}
        if is_search_budget_exhausted(item.name, prior_log):
            logger.info('[agent] search budget blocked tool=%s iteration=%d', item.name, iteration)
            result = search_budget_message(item.name, prior_log)
        else:
            result = await execute_tool(item.name, args)
            await schedule_tool_ingest(item.name, args, result, task=task)
        return (item, args, result)
    triples = await asyncio.gather(*[_run(call) for call in call_items])
    outputs, log_entries = ([], [])
    for item, args, result in triples:
        log_entries.append({'tool': item.name, 'inputs': args, 'result': result})
        outputs.append({'type': 'function_call_output', 'call_id': item.call_id, 'output': serialize_result(result)})
    return (outputs, log_entries)
