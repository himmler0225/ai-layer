import json
from app.config.logger import Logger
from typing import Any, AsyncGenerator, Dict, List

import anthropic

import uuid
import app.config.settings as _cfg
import app.services.prompts as _prompts
from app.tools.executor import execute_tool
from app.services.enricher import enrich_agent_result
from app.db.mongo import log_tool_call, log_agent_run

logger = Logger.get(__name__)

def _client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=_cfg.ANTHROPIC_API_KEY)

def _max_result_chars() -> int: return _cfg.AGENT_MAX_RESULT_CHARS
def _max_comments()     -> int: return _cfg.AGENT_MAX_COMMENTS
def _max_comment_len()  -> int: return _cfg.AGENT_MAX_COMMENT_LEN
def _max_list_items()   -> int: return _cfg.AGENT_MAX_LIST_ITEMS

def _serialize_result(result: Dict) -> str:
    if not isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False, default=str)[:_max_result_chars()]

    data = dict(result)

    if "comments" in data and isinstance(data["comments"], list):
        data["comments"] = [
            {**c, "content": (c.get("content") or c.get("text") or "")[:_max_comment_len()]}
            for c in data["comments"][:_max_comments()]
        ]

    # Video / product lists: cap count + trim descriptions
    for list_key in ("videos", "products", "results", "items"):
        if list_key in data and isinstance(data[list_key], list):
            trimmed = []
            for item in data[list_key][:_max_list_items()]:
                if isinstance(item, dict) and "description" in item:
                    item = {**item, "description": (item["description"] or "")[:200]}
                trimmed.append(item)
            data[list_key] = trimmed

    serialized = json.dumps(data, ensure_ascii=False, default=str)

    if len(serialized) > _max_result_chars():
        serialized = serialized[:_max_result_chars()] + '... [truncated]"}'

    return serialized

async def run_agent(
    task: str,
    tools: List[Dict],
    max_iter: int = 10,
    system: str = None,
) -> Dict[str, Any]:
    if system is None:
        system = _prompts.AGENT_SYSTEM
    session_id = str(uuid.uuid4())
    messages: List[Dict] = [{"role": "user", "content": task}]
    tool_call_log: List[Dict] = []

    has_history = "\n[Câu hỏi hiện tại]\n" in task

    for iteration in range(1, max_iter + 1):
        logger.info("Agent iteration %d/%d", iteration, max_iter)

        force_tool = iteration == 1 and not tool_call_log and not has_history
        tool_choice = {"type": "any"} if force_tool else {"type": "auto"}

        response = await _client().messages.stream(
            model=_cfg.CLAUDE_MODEL,
            max_tokens=_cfg.CLAUDE_MAX_TOKENS,
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
            enriched1 = await enrich_agent_result(final_text, tool_call_log, iteration)
            await log_agent_run(session_id, task, iteration, tool_call_log, final_text, enriched1["data"].get("sources",[]), enriched1["data"].get("videos",[]), enriched1["data"].get("reviews_analyzed",0))
            return enriched1

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
                await log_tool_call(session_id, task, block.name, dict(block.input), result, iteration)

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

async def run_agent_stream(
    task: str,
    tools: List[Dict],
    max_iter: int = 10,
    system: str = None,
) -> AsyncGenerator[str, None]:
    if system is None:
        system = _prompts.AGENT_SYSTEM
    session_id = str(uuid.uuid4())
    messages: List[Dict] = [{"role": "user", "content": task}]
    tool_call_log: List[Dict] = []
    has_history = "\n[Câu hỏi hiện tại]\n" in task

    def _sse(data: Dict) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    for iteration in range(1, max_iter + 1):
        force_tool = iteration == 1 and not tool_call_log and not has_history
        tool_choice = {"type": "any"} if force_tool else {"type": "auto"}

        collected_text = ""

        async with _client().messages.stream(
            model=_cfg.CLAUDE_MODEL,
            max_tokens=_cfg.CLAUDE_MAX_TOKENS,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=tools,
            tool_choice=tool_choice,
            messages=messages,
        ) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta" and delta.text:
                        collected_text += delta.text
                        yield _sse({"type": "text_delta", "delta": delta.text})

            final = await stream.get_final_message()

        if final.stop_reason == "end_turn":
            enriched = await enrich_agent_result(collected_text, tool_call_log, iteration)
            await log_agent_run(
                session_id, task, iteration, tool_call_log,
                collected_text,
                enriched["data"].get("sources", []),
                enriched["data"].get("videos", []),
                enriched["data"].get("reviews_analyzed", 0),
            )
            yield _sse({
                "type":       "done",
                "data":       enriched["data"],
                "tool_calls": enriched["tool_calls"],
            })
            return

        if final.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": final.content})
            tool_results = []
            for block in final.content:
                if block.type != "tool_use":
                    continue
                yield _sse({"type": "tool_start", "tool": block.name})
                result = await execute_tool(block.name, block.input)
                tool_call_log.append({"tool": block.name, "inputs": block.input, "result": result})
                await log_tool_call(session_id, task, block.name, dict(block.input), result, iteration)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": _serialize_result(result),
                })
                yield _sse({"type": "tool_done", "tool": block.name})
            messages.append({"role": "user", "content": tool_results})
            continue

        yield _sse({"type": "error", "message": f"Unexpected stop_reason: {final.stop_reason}"})
        return

    yield _sse({"type": "error", "message": f"Agent did not finish within {max_iter} iterations"})
