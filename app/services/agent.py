import asyncio
import json
from app.config.logger import Logger
from typing import Any, AsyncGenerator, Dict, List, Tuple

import anthropic

import uuid
import app.config.settings as _cfg
import app.services.prompts as _prompts
from app.tools.executor import execute_tool
from app.services.enricher import enrich_agent_result
from app.db.mongo import log_tool_call, log_agent_run

logger = Logger.get(__name__)


def _client() -> anthropic.AsyncAnthropic:
    if not _cfg.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not configured — set it in Supabase config table")
    if not _cfg.CLAUDE_MODEL:
        raise RuntimeError("CLAUDE_MODEL not configured — set it in Supabase config table")
    return anthropic.AsyncAnthropic(api_key=_cfg.ANTHROPIC_API_KEY)

def _tool_model() -> str:
    return _cfg.CLAUDE_TOOL_MODEL or _cfg.CLAUDE_MODEL

def _synth_model() -> str:
    return _cfg.CLAUDE_MODEL

def _dual_mode() -> bool:
    return bool(_cfg.CLAUDE_TOOL_MODEL) and _cfg.CLAUDE_TOOL_MODEL != _cfg.CLAUDE_MODEL

def _tool_max_tokens() -> int:
    return _cfg.CLAUDE_TOOL_MAX_TOKENS if _dual_mode() else _cfg.CLAUDE_MAX_TOKENS

def _synth_max_tokens() -> int:
    return _cfg.CLAUDE_MAX_TOKENS

def _max_result_chars() -> int: return _cfg.AGENT_MAX_RESULT_CHARS
def _max_comments()     -> int: return _cfg.AGENT_MAX_COMMENTS
def _max_comment_len()  -> int: return _cfg.AGENT_MAX_COMMENT_LEN
def _max_list_items()   -> int: return _cfg.AGENT_MAX_LIST_ITEMS

async def _execute_tools_parallel(
    blocks: List[Any],
    session_id: str,
    task: str,
    iteration: int,
) -> Tuple[List[Dict], List[Dict]]:
    """Execute all tool_use blocks in parallel. Returns (tool_results, tool_call_log_entries)."""
    tool_blocks = [b for b in blocks if b.type == "tool_use"]
    if not tool_blocks:
        return [], []

    logger.info("Executing %d tool(s) in parallel: %s", len(tool_blocks), [b.name for b in tool_blocks])

    async def _run(block: Any) -> Tuple[Any, Any]:
        result = await execute_tool(block.name, block.input)
        await log_tool_call(session_id, task, block.name, dict(block.input), result, iteration)
        return block, result

    pairs = await asyncio.gather(*[_run(b) for b in tool_blocks])

    tool_results = []
    log_entries = []
    for block, result in pairs:
        log_entries.append({"tool": block.name, "inputs": block.input, "result": result})
        tool_results.append({
            "type":        "tool_result",
            "tool_use_id": block.id,
            "content":     _serialize_result(result),
        })
    return tool_results, log_entries


def _serialize_result(result: Dict) -> str:
    if not isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False, default=str)[:_max_result_chars()]

    data = dict(result)

    if "comments" in data and isinstance(data["comments"], list):
        data["comments"] = [
            {**c, "content": (c.get("content") or c.get("text") or "")[:_max_comment_len()]}
            for c in data["comments"][:_max_comments()]
        ]

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
    sys_block = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

    for iteration in range(1, max_iter + 1):
        logger.info("Agent iteration %d/%d model=%s", iteration, max_iter, _tool_model())

        force_tool = iteration == 1 and not tool_call_log and not has_history
        tool_choice = {"type": "any"} if force_tool else {"type": "auto"}

        response = await _client().messages.stream(
            model=_tool_model(),
            max_tokens=_tool_max_tokens(),
            system=sys_block,
            tools=tools,
            tool_choice=tool_choice,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            if _dual_mode() and tool_call_log:
                logger.info("Synthesis pass model=%s max_tokens=%d", _synth_model(), _synth_max_tokens())
                synth = await _client().messages.create(
                    model=_synth_model(),
                    max_tokens=_synth_max_tokens(),
                    system=sys_block,
                    messages=messages,
                )
                final_text = "".join(getattr(b, "text", "") for b in synth.content)
            else:
                final_text = "".join(getattr(b, "text", "") for b in response.content)

            enriched = await enrich_agent_result(final_text, tool_call_log, iteration)
            await log_agent_run(
                session_id, task, iteration, tool_call_log, final_text,
                enriched["data"].get("sources", []),
                enriched["data"].get("videos", []),
                enriched["data"].get("reviews_analyzed", 0),
            )
            return enriched

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results, log_entries = await _execute_tools_parallel(
                response.content, session_id, task, iteration
            )
            tool_call_log.extend(log_entries)
            messages.append({"role": "user", "content": tool_results})
            continue

        if response.stop_reason == "max_tokens":
            if _dual_mode() and tool_call_log:
                logger.warning("max_tokens hit at iteration %d (dual mode) — falling through to Opus synthesis", iteration)
                synth = await _client().messages.create(
                    model=_synth_model(),
                    max_tokens=_synth_max_tokens(),
                    system=sys_block,
                    messages=messages,
                )
                final_text = "".join(getattr(b, "text", "") for b in synth.content)
                enriched = await enrich_agent_result(final_text, tool_call_log, iteration)
                await log_agent_run(session_id, task, iteration, tool_call_log, final_text,
                    enriched["data"].get("sources", []), enriched["data"].get("videos", []),
                    enriched["data"].get("reviews_analyzed", 0))
                return enriched
            partial = "".join(getattr(b, "text", "") for b in response.content)
            if partial:
                return await enrich_agent_result(partial, tool_call_log, iteration)
            raise RuntimeError(f"Claude hit max_tokens at iteration {iteration} without text.")

        logger.error("Unexpected stop_reason=%r at iteration %d", response.stop_reason, iteration)
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
    sys_block = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

    def _sse(data: Dict) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    for iteration in range(1, max_iter + 1):
        force_tool = iteration == 1 and not tool_call_log and not has_history
        tool_choice = {"type": "any"} if force_tool else {"type": "auto"}

        async with _client().messages.stream(
            model=_tool_model(),
            max_tokens=_tool_max_tokens(),
            system=sys_block,
            tools=tools,
            tool_choice=tool_choice,
            messages=messages,
        ) as stream:
            # In dual-mode: don't stream Haiku's text — only Opus's final answer gets streamed.
            # In single-mode: stream text normally.
            async for event in stream:
                if not _dual_mode() and event.type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta" and delta.text:
                        yield _sse({"type": "text_delta", "delta": delta.text})

            final = await stream.get_final_message()

        if final.stop_reason == "end_turn":
            if _dual_mode() and tool_call_log:
                # Haiku done — stream Opus synthesis
                logger.info("Synthesis stream model=%s max_tokens=%d", _synth_model(), _synth_max_tokens())
                opus_text = ""
                async with _client().messages.stream(
                    model=_synth_model(),
                    max_tokens=_synth_max_tokens(),
                    system=sys_block,
                    messages=messages,
                ) as opus_stream:
                    async for event in opus_stream:
                        if event.type == "content_block_delta":
                            delta = event.delta
                            if delta.type == "text_delta" and delta.text:
                                opus_text += delta.text
                                yield _sse({"type": "text_delta", "delta": delta.text})
                    final_opus = await opus_stream.get_final_message()

                collected_text = opus_text
                logger.info("Opus synthesis done stop_reason=%s chars=%d", final_opus.stop_reason, len(opus_text))
            else:
                collected_text = "".join(getattr(b, "text", "") for b in final.content)

            enriched = await enrich_agent_result(collected_text, tool_call_log, iteration)
            await log_agent_run(
                session_id, task, iteration, tool_call_log,
                collected_text,
                enriched["data"].get("sources", []),
                enriched["data"].get("videos", []),
                enriched["data"].get("reviews_analyzed", 0),
            )
            yield _sse({"type": "done", "data": enriched["data"], "tool_calls": enriched["tool_calls"]})
            return

        if final.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": final.content})
            tool_names = [b.name for b in final.content if b.type == "tool_use"]
            for name in tool_names:
                yield _sse({"type": "tool_start", "tool": name})
            tool_results, log_entries = await _execute_tools_parallel(
                final.content, session_id, task, iteration
            )
            tool_call_log.extend(log_entries)
            for name in tool_names:
                yield _sse({"type": "tool_done", "tool": name})

            # Emit preview of data collected 
            preview_videos: List[Dict] = []
            for entry in tool_call_log:
                for v in (entry.get("result") or {}).get("videos") or []:
                    if isinstance(v, dict) and v.get("video_id"):
                        preview_videos.append(v)
            if preview_videos:
                seen: set = set()
                unique = [v for v in preview_videos if not (v["video_id"] in seen or seen.add(v["video_id"]))]
                yield _sse({"type": "data_preview", "videos": unique[:10]})

            messages.append({"role": "user", "content": tool_results})
            continue

        if final.stop_reason == "max_tokens":
            if _dual_mode() and tool_call_log:
                logger.warning("max_tokens hit at iteration %d (dual mode) — falling through to Opus synthesis", iteration)
                opus_text = ""
                async with _client().messages.stream(
                    model=_synth_model(),
                    max_tokens=_synth_max_tokens(),
                    system=sys_block,
                    messages=messages,
                ) as opus_stream:
                    async for event in opus_stream:
                        if event.type == "content_block_delta":
                            delta = event.delta
                            if delta.type == "text_delta" and delta.text:
                                opus_text += delta.text
                                yield _sse({"type": "text_delta", "delta": delta.text})
                enriched = await enrich_agent_result(opus_text, tool_call_log, iteration)
                yield _sse({"type": "done", "data": enriched["data"], "tool_calls": enriched["tool_calls"]})
                return
            partial = "".join(getattr(b, "text", "") for b in final.content)
            if partial:
                logger.warning("max_tokens hit at iteration %d — returning partial text", iteration)
                enriched = await enrich_agent_result(partial, tool_call_log, iteration)
                yield _sse({"type": "done", "data": enriched["data"], "tool_calls": enriched["tool_calls"]})
                return
            yield _sse({"type": "error", "message": "max_tokens reached without output — try increasing CLAUDE_MAX_TOKENS"})
            return

        yield _sse({"type": "error", "message": f"Unexpected stop_reason: {final.stop_reason}"})
        return

    yield _sse({"type": "error", "message": f"Agent did not finish within {max_iter} iterations"})
