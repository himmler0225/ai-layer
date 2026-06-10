import json
from app.config.logger import Logger
from typing import Any, Dict, List

import anthropic

from app.config.settings import (
    ANTHROPIC_API_KEY, CLAUDE_MODEL, CLAUDE_MAX_TOKENS,
    AGENT_MAX_RESULT_CHARS as _MAX_RESULT_CHARS,
    AGENT_MAX_COMMENTS     as _MAX_COMMENTS,
    AGENT_MAX_COMMENT_LEN  as _MAX_COMMENT_LEN,
    AGENT_MAX_LIST_ITEMS   as _MAX_LIST_ITEMS,
)
from app.tools.executor import execute_tool
from app.services.enricher import enrich_agent_result
from app.services.prompts import AGENT_SYSTEM

logger = Logger.get(__name__)

_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

def _serialize_result(result: Dict) -> str:
    if not isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False, default=str)[:_MAX_RESULT_CHARS]

    data = dict(result)

    if "comments" in data and isinstance(data["comments"], list):
        data["comments"] = [
            {**c, "content": (c.get("content") or c.get("text") or "")[:_MAX_COMMENT_LEN]}
            for c in data["comments"][:_MAX_COMMENTS]
        ]

    # Video / product lists: cap count + trim descriptions
    for list_key in ("videos", "products", "results", "items"):
        if list_key in data and isinstance(data[list_key], list):
            trimmed = []
            for item in data[list_key][:_MAX_LIST_ITEMS]:
                if isinstance(item, dict) and "description" in item:
                    item = {**item, "description": (item["description"] or "")[:200]}
                trimmed.append(item)
            data[list_key] = trimmed

    serialized = json.dumps(data, ensure_ascii=False, default=str)

    if len(serialized) > _MAX_RESULT_CHARS:
        serialized = serialized[:_MAX_RESULT_CHARS] + '... [truncated]"}'

    return serialized

async def run_agent(
    task: str,
    tools: List[Dict],
    max_iter: int = 10,
    system: str = AGENT_SYSTEM,
) -> Dict[str, Any]:
    messages: List[Dict] = [{"role": "user", "content": task}]
    tool_call_log: List[Dict] = []

    has_history = "\n[Câu hỏi hiện tại]\n" in task

    for iteration in range(1, max_iter + 1):
        logger.info("Agent iteration %d/%d", iteration, max_iter)

        force_tool = iteration == 1 and not tool_call_log and not has_history
        tool_choice = {"type": "any"} if force_tool else {"type": "auto"}

        response = await _client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=tools,
            tool_choice=tool_choice,
            messages=messages,
        )

        logger.info("stop_reason=%s  content_blocks=%d", response.stop_reason, len(response.content))

        if response.stop_reason == "end_turn":
            final_text = "".join(
                getattr(b, "text", "") for b in response.content
            )
            return await enrich_agent_result(final_text, tool_call_log, iteration)

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                logger.info("Tool call: %s  inputs=%s", block.name, block.input)
                result = await execute_tool(block.name, block.input)

                tool_call_log.append({
                    "tool":   block.name,
                    "inputs": block.input,
                    "result": result,
                })

                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": block.id,
                    "content":     _serialize_result(result),
                })

            messages.append({"role": "user", "content": tool_results})
            continue

        if response.stop_reason == "max_tokens":
            partial = "".join(getattr(b, "text", "") for b in response.content)
            logger.warning(
                "Claude hit max_tokens at iteration %d (partial text: %d chars, tool_calls so far: %d)",
                iteration, len(partial), len(tool_call_log),
            )
            if partial:
                return await enrich_agent_result(partial, tool_call_log, iteration)
            raise RuntimeError(
                f"Claude hit max_tokens at iteration {iteration} without producing text. "
                "Try increasing CLAUDE_MAX_TOKENS or simplifying the task."
            )

        logger.error(
            "Unexpected stop_reason=%r at iteration %d — aborting agent loop",
            response.stop_reason, iteration,
        )
        break

    raise RuntimeError(f"Agent did not finish within {max_iter} iterations")
