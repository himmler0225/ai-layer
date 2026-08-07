import asyncio
import json
from typing import Any
from app.config.logger import Logger, log_event
from app.ingest.dispatcher.schedule import schedule_tool_ingest
from app.services.agent.guards import is_search_budget_exhausted, search_budget_message
from app.services.agent.tooling.serialize import serialize_result
from app.tools.executor import execute_tool

logger = Logger.get(__name__)


def extract_function_calls(output: list[Any]) -> list[Any]:
    """Filter a model response's output items down to just the function/tool call items.

    Args:
        output: (List[Any]) Raw output items from an LLM response.

    Returns:
        (List[Any]) Items whose type is "function_call"."""
    return [item for item in output if getattr(item, "type", None) == "function_call"]


async def execute_parallel(
    output: list[Any], session_id: str, task: str, iteration: int, *, tool_call_log: list[dict] | None = None
) -> tuple[list[dict], list[dict]]:
    """Execute all pending tool calls concurrently, respecting the search budget (async).

    Calls found in `output` are run in parallel via asyncio.gather; any call
    whose tool has already hit its search budget is short-circuited with a
    budget-exhausted message instead of actually being executed. Successful
    calls also get scheduled for ingest.

    Args:
        output: (List[Any]) Raw LLM response output items to scan for tool calls.
        session_id: (str) Current agent run session id (currently unused directly, kept for interface consistency).
        task: (str) The original user task, passed through to ingest scheduling.
        iteration: (int) Current tool-round iteration number, used for logging.
        tool_call_log: (list[dict] | None) Prior tool call log, used to check the search budget.

    Returns:
        (Tuple[List[Dict], List[Dict]]) A tuple of (function_call_output items
        to feed back to the LLM, tool_call_log entries recording tool/inputs/result)."""
    call_items = extract_function_calls(output)
    if not call_items:
        return ([], [])
    logger.info(
        log_event("agent", "executing tools", count=len(call_items), names=[call.name for call in call_items])
    )

    prior_log = tool_call_log or []

    async def _run(item: Any):
        """(Internal) Execute a single tool call, or short-circuit it if its search budget is exhausted (async).

        Args:
            item: (Any) Function call item with `.name`, `.arguments`, and `.call_id`.

        Returns:
            (tuple) The (item, parsed_args, result) triple for this call."""
        try:
            args = json.loads(item.arguments) if item.arguments else {}
        except json.JSONDecodeError:
            logger.error(log_event("agent", "invalid tool args", tool=item.name, raw=item.arguments))
            args = {}
        if is_search_budget_exhausted(item.name, prior_log):
            logger.info(log_event("agent", "search budget blocked", tool=item.name, iteration=iteration))
            result = search_budget_message(item.name, prior_log)
        else:
            result = await execute_tool(item.name, args)
            await schedule_tool_ingest(item.name, args, result, task=task)
        return (item, args, result)

    triples = await asyncio.gather(*[_run(call) for call in call_items])
    outputs, log_entries = ([], [])
    for item, args, result in triples:
        log_entries.append({"tool": item.name, "inputs": args, "result": result})
        outputs.append({"type": "function_call_output", "call_id": item.call_id, "output": serialize_result(result)})
    return (outputs, log_entries)
