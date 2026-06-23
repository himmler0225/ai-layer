import asyncio
import json
import re
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import app.config.settings as _cfg
import app.services.prompts as _prompts
from app.config.logger import Logger
from app.db.mongo import log_agent_run, log_tool_call
from app.services.enricher import enrich_agent_result
from app.tools.executor import execute_tool
from app.utils.openai_client import get_openai_client
from app.utils.openai_responses import (
    create_response,
    extract_response_text,
    is_incomplete_for,
    output_items_to_input,
    status_error,
)

logger = Logger.get(__name__)


def _tool_model() -> str:
    return _cfg.OPENAI_TOOL_MODEL or _cfg.OPENAI_MODEL


def _synth_model() -> str:
    return _cfg.OPENAI_MODEL


def _dual_mode() -> bool:
    return bool(_cfg.OPENAI_TOOL_MODEL) and _cfg.OPENAI_TOOL_MODEL != _cfg.OPENAI_MODEL


def _tool_max_tokens() -> int:
    return _cfg.OPENAI_TOOL_MAX_TOKENS if _dual_mode() else _cfg.OPENAI_MAX_TOKENS


def _synth_max_tokens() -> int:
    return _cfg.OPENAI_MAX_TOKENS


def _max_result_chars() -> int:
    return _cfg.AGENT_MAX_RESULT_CHARS


def _max_comments() -> int:
    return _cfg.AGENT_MAX_COMMENTS


def _max_comment_len() -> int:
    return _cfg.AGENT_MAX_COMMENT_LEN


def _max_list_items() -> int:
    return _cfg.AGENT_MAX_LIST_ITEMS


def _extract_function_calls(output: List[Any]) -> List[Any]:
    return [item for item in output if getattr(item, "type", None) == "function_call"]


_HISTORY_MARKER = "\n[Câu hỏi hiện tại]\n"
_TIKTOK_PATTERN = re.compile(r"\btiktok\b", re.IGNORECASE)
_YOUTUBE_PATTERN = re.compile(r"\byoutube\b", re.IGNORECASE)


def _current_question(task: str) -> str:
    if _HISTORY_MARKER in task:
        return task.split(_HISTORY_MARKER)[-1]
    return task


def _detect_platform(task: str) -> Optional[str]:
    question = _current_question(task)
    has_tiktok = bool(_TIKTOK_PATTERN.search(question))
    has_youtube = bool(_YOUTUBE_PATTERN.search(question))
    if has_tiktok and not has_youtube:
        return "tiktok"
    if has_youtube and not has_tiktok:
        return "youtube"
    return None


def _filter_tools_by_platform(tools: List[Dict], task: str) -> List[Dict]:
    platform = _detect_platform(task)
    if platform is None:
        return tools

    blocked_prefix = "tiktok_" if platform == "youtube" else "youtube_"
    filtered = [tool for tool in tools if not tool.get("name", "").startswith(blocked_prefix)]

    if len(filtered) != len(tools):
        logger.info(
            "[agent] platform=%s blocked=%s* tools=%d/%d",
            platform,
            blocked_prefix,
            len(filtered),
            len(tools),
        )
    return filtered


async def _execute_tools_parallel(
    output: List[Any],
    session_id: str,
    task: str,
    iteration: int,
) -> Tuple[List[Dict], List[Dict]]:
    call_items = _extract_function_calls(output)
    if not call_items:
        return [], []

    logger.info(
        "[agent] executing tools count=%d names=%s",
        len(call_items),
        [call.name for call in call_items],
    )

    async def _run(item: Any) -> Tuple[Any, Dict, Any]:
        try:
            args = json.loads(item.arguments) if item.arguments else {}
        except json.JSONDecodeError:
            logger.error("[agent] invalid tool args tool=%s raw=%r", item.name, item.arguments)
            args = {}
        result = await execute_tool(item.name, args)
        await log_tool_call(session_id, task, item.name, args, result, iteration)
        return item, args, result

    triples = await asyncio.gather(*[_run(call) for call in call_items])

    function_call_outputs = []
    log_entries = []
    for item, args, result in triples:
        log_entries.append({"tool": item.name, "inputs": args, "result": result})
        function_call_outputs.append({
            "type": "function_call_output",
            "call_id": item.call_id,
            "output": _serialize_result(result),
        })
    return function_call_outputs, log_entries


def _serialize_result(result: Dict) -> str:
    if not isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False, default=str)[:_max_result_chars()]

    data = dict(result)

    if "comments" in data and isinstance(data["comments"], list):
        data["comments"] = [
            {**comment, "content": (comment.get("content") or comment.get("text") or "")[:_max_comment_len()]}
            for comment in data["comments"][:_max_comments()]
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


async def _run_synthesis(
    *,
    system: str,
    input_items: List[Dict],
) -> str:
    response = await create_response(
        model=_synth_model(),
        max_output_tokens=_synth_max_tokens(),
        instructions=system,
        input=input_items,
    )
    err = status_error(response)
    if err:
        raise RuntimeError(err)
    return extract_response_text(response)


async def run_agent(
    task: str,
    tools: List[Dict],
    max_iter: int = 10,
    system: str = None,
) -> Dict[str, Any]:
    if system is None:
        system = _prompts.AGENT_SYSTEM

    tools = _filter_tools_by_platform(tools, task)

    session_id = str(uuid.uuid4())
    input_items: List[Dict] = [{"role": "user", "content": task}]
    tool_call_log: List[Dict] = []
    has_history = _HISTORY_MARKER in task

    for iteration in range(1, max_iter + 1):
        logger.info("[agent] iteration=%d/%d model=%s", iteration, max_iter, _tool_model())

        force_tool = iteration == 1 and not tool_call_log and not has_history
        tool_choice = "required" if force_tool else "auto"

        response = await create_response(
            model=_tool_model(),
            max_output_tokens=_tool_max_tokens(),
            instructions=system,
            tools=tools,
            tool_choice=tool_choice,
            input=input_items,
        )

        err = status_error(response)
        if err:
            raise RuntimeError(err)

        if is_incomplete_for("max_output_tokens", response):
            if _dual_mode() and tool_call_log:
                logger.warning(
                    "[agent] max_output_tokens iteration=%d mode=dual_synthesis",
                    iteration,
                )
                input_items.extend(output_items_to_input(response.output))
                final_text = await _run_synthesis(system=system, input_items=input_items)
                enriched = await enrich_agent_result(final_text, tool_call_log, iteration, task=task)
                await log_agent_run(
                    session_id,
                    task,
                    iteration,
                    tool_call_log,
                    final_text,
                    enriched["data"].get("sources", []),
                    enriched["data"].get("videos", []),
                    enriched["data"].get("reviews_analyzed", 0),
                )
                return enriched

            partial = extract_response_text(response)
            if partial:
                return await enrich_agent_result(partial, tool_call_log, iteration, task=task)
            raise RuntimeError(f"Model hit max_output_tokens at iteration {iteration} without text.")

        call_items = _extract_function_calls(response.output)
        if call_items:
            input_items.extend(output_items_to_input(response.output))
            function_call_outputs, log_entries = await _execute_tools_parallel(
                response.output,
                session_id,
                task,
                iteration,
            )
            tool_call_log.extend(log_entries)
            input_items.extend(function_call_outputs)
            continue

        if _dual_mode() and tool_call_log:
            logger.info(
                "[agent] synthesis model=%s max_tokens=%d",
                _synth_model(),
                _synth_max_tokens(),
            )
            input_items.extend(output_items_to_input(response.output))
            final_text = await _run_synthesis(system=system, input_items=input_items)
        else:
            final_text = extract_response_text(response)

        enriched = await enrich_agent_result(final_text, tool_call_log, iteration, task=task)
        await log_agent_run(
            session_id,
            task,
            iteration,
            tool_call_log,
            final_text,
            enriched["data"].get("sources", []),
            enriched["data"].get("videos", []),
            enriched["data"].get("reviews_analyzed", 0),
        )
        return enriched

    raise RuntimeError(f"Agent did not finish within {max_iter} iterations")


async def run_agent_stream(
    task: str,
    tools: List[Dict],
    max_iter: int = 10,
    system: str = None,
) -> AsyncGenerator[str, None]:
    if system is None:
        system = _prompts.AGENT_SYSTEM

    tools = _filter_tools_by_platform(tools, task)

    session_id = str(uuid.uuid4())
    input_items: List[Dict] = [{"role": "user", "content": task}]
    tool_call_log: List[Dict] = []
    has_history = _HISTORY_MARKER in task

    def _sse(data: Dict) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    for iteration in range(1, max_iter + 1):
        force_tool = iteration == 1 and not tool_call_log and not has_history
        tool_choice = "required" if force_tool else "auto"

        async with get_openai_client().responses.stream(
            model=_tool_model(),
            max_output_tokens=_tool_max_tokens(),
            instructions=system,
            tools=tools,
            tool_choice=tool_choice,
            input=input_items,
        ) as stream:
            async for event in stream:
                if not _dual_mode() and event.type == "response.output_text.delta":
                    yield _sse({"type": "text_delta", "delta": event.delta})

            final = await stream.get_final_response()

        err = status_error(final)
        if err:
            yield _sse({"type": "error", "message": err})
            return

        if is_incomplete_for("max_output_tokens", final):
            if _dual_mode() and tool_call_log:
                logger.warning(
                    "[agent] max_output_tokens iteration=%d mode=dual_synthesis_stream",
                    iteration,
                )
                input_items.extend(output_items_to_input(final.output))
                synth_text = ""
                async with get_openai_client().responses.stream(
                    model=_synth_model(),
                    max_output_tokens=_synth_max_tokens(),
                    instructions=system,
                    input=input_items,
                ) as synth_stream:
                    async for event in synth_stream:
                        if event.type == "response.output_text.delta":
                            synth_text += event.delta
                            yield _sse({"type": "text_delta", "delta": event.delta})
                enriched = await enrich_agent_result(synth_text, tool_call_log, iteration, task=task)
                yield _sse({"type": "done", "data": enriched["data"], "tool_calls": enriched["tool_calls"]})
                return

            partial = extract_response_text(final)
            if partial:
                logger.warning("[agent] max_output_tokens iteration=%d partial=true", iteration)
                enriched = await enrich_agent_result(partial, tool_call_log, iteration, task=task)
                yield _sse({"type": "done", "data": enriched["data"], "tool_calls": enriched["tool_calls"]})
                return

            yield _sse({
                "type": "error",
                "message": "max_output_tokens reached without output — try increasing OPENAI_MAX_TOKENS",
            })
            return

        call_items = _extract_function_calls(final.output)
        if call_items:
            input_items.extend(output_items_to_input(final.output))
            tool_names = [call.name for call in call_items]
            for name in tool_names:
                yield _sse({"type": "tool_start", "tool": name})

            function_call_outputs, log_entries = await _execute_tools_parallel(
                final.output,
                session_id,
                task,
                iteration,
            )
            tool_call_log.extend(log_entries)

            for name in tool_names:
                yield _sse({"type": "tool_done", "tool": name})

            preview_videos: List[Dict] = []
            for entry in tool_call_log:
                for video in (entry.get("result") or {}).get("videos") or []:
                    if isinstance(video, dict) and video.get("video_id"):
                        preview_videos.append(video)

            if preview_videos:
                seen: set = set()
                unique = [
                    video
                    for video in preview_videos
                    if not (video["video_id"] in seen or seen.add(video["video_id"]))
                ]
                yield _sse({"type": "data_preview", "videos": unique[:10]})

            input_items.extend(function_call_outputs)
            continue

        if _dual_mode() and tool_call_log:
            logger.info(
                "[agent] synthesis_stream model=%s max_tokens=%d",
                _synth_model(),
                _synth_max_tokens(),
            )
            input_items.extend(output_items_to_input(final.output))
            synth_text = ""
            async with get_openai_client().responses.stream(
                model=_synth_model(),
                max_output_tokens=_synth_max_tokens(),
                instructions=system,
                input=input_items,
            ) as synth_stream:
                async for event in synth_stream:
                    if event.type == "response.output_text.delta":
                        synth_text += event.delta
                        yield _sse({"type": "text_delta", "delta": event.delta})
                final_synth = await synth_stream.get_final_response()
            collected_text = synth_text
            logger.info(
                "[agent] synthesis_done status=%s chars=%d",
                final_synth.status,
                len(synth_text),
            )
        else:
            collected_text = extract_response_text(final)

        enriched = await enrich_agent_result(collected_text, tool_call_log, iteration, task=task)
        await log_agent_run(
            session_id,
            task,
            iteration,
            tool_call_log,
            collected_text,
            enriched["data"].get("sources", []),
            enriched["data"].get("videos", []),
            enriched["data"].get("reviews_analyzed", 0),
        )
        yield _sse({"type": "done", "data": enriched["data"], "tool_calls": enriched["tool_calls"]})
        return

    yield _sse({"type": "error", "message": f"Agent did not finish within {max_iter} iterations"})
