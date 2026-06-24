from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Tuple

from app.config.logger import Logger
from app.db.mongo import log_tool_call
from app.ingest.dispatcher import schedule_tool_ingest
from app.services.agent.serialize import serialize_result
from app.tools.executor import execute_tool

logger = Logger.get(__name__)


def extract_function_calls(output: List[Any]) -> List[Any]:
    """Lọc các lệnh gọi tool từ response OpenAI."""
    return [item for item in output if getattr(item, "type", None) == "function_call"]


async def execute_parallel(
    output: List[Any],
    session_id: str,
    task: str,
    iteration: int,
) -> Tuple[List[Dict], List[Dict]]:
    """Gọi nhiều tool song song trong một iteration."""
    call_items = extract_function_calls(output)
    if not call_items:
        return [], []

    logger.info(
        "[agent] executing tools count=%d names=%s",
        len(call_items),
        [call.name for call in call_items],
    )

    async def _run(item: Any):
        """Chạy một tool call và ghi log."""
        try:
            args = json.loads(item.arguments) if item.arguments else {}
        except json.JSONDecodeError:
            logger.error("[agent] invalid tool args tool=%s raw=%r", item.name, item.arguments)
            args = {}
        result = await execute_tool(item.name, args)
        await schedule_tool_ingest(item.name, args, result, task=task)
        await log_tool_call(session_id, task, item.name, args, result, iteration)
        return item, args, result

    triples = await asyncio.gather(*[_run(call) for call in call_items])

    outputs, log_entries = [], []
    for item, args, result in triples:
        log_entries.append({"tool": item.name, "inputs": args, "result": result})
        outputs.append({
            "type": "function_call_output",
            "call_id": item.call_id,
            "output": serialize_result(result),
        })
    return outputs, log_entries