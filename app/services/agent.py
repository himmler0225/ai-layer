import asyncio
import json
import re
from app.config.logger import Logger
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import uuid
import app.config.settings as _cfg
import app.services.prompts as _prompts
from app.utils.openai_client import get_openai_client
from app.tools.executor import execute_tool
from app.services.enricher import enrich_agent_result
from app.db.mongo import log_tool_call, log_agent_run

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

def _max_result_chars() -> int: return _cfg.AGENT_MAX_RESULT_CHARS
def _max_comments()     -> int: return _cfg.AGENT_MAX_COMMENTS
def _max_comment_len()  -> int: return _cfg.AGENT_MAX_COMMENT_LEN
def _max_list_items()   -> int: return _cfg.AGENT_MAX_LIST_ITEMS


def _extract_function_calls(output: List[Any]) -> List[Any]:
    """Pick out function_call items from a Responses API `output` list."""
    return [item for item in output if getattr(item, "type", None) == "function_call"]


def _extract_text(response: Any) -> str:
    """The Responses API object exposes a convenience `.output_text` that
    concatenates every output_text block. Fall back to manual concatenation
    if it isn't present (e.g. on an older SDK version)."""
    text = getattr(response, "output_text", None)
    if text is not None:
        return text
    chunks = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) == "message":
            for c in item.content:
                if getattr(c, "type", None) == "output_text":
                    chunks.append(c.text)
    return "".join(chunks)


def _is_incomplete_for(reason: str, response: Any) -> bool:
    return (
        getattr(response, "status", None) == "incomplete"
        and getattr(response, "incomplete_details", None) is not None
        and getattr(response.incomplete_details, "reason", None) == reason
    )


def _output_item_to_input(item: Any) -> Dict:
    """Convert a Responses API *output* item back into the shape the API
    accepts for the next turn's `input=`.

    The SDK's output objects carry extra computed/convenience fields
    (e.g. `parsed_arguments`, `id`, `status`) that exist only on output —
    echoing them back verbatim in `input` triggers
    `Unknown parameter: 'input[i].parsed_arguments'` (or similar) from the
    API. So we keep only the fields each item type actually accepts as
    input.
    """
    item_type = getattr(item, "type", None)

    if item_type == "function_call":
        return {
            "type": "function_call",
            "call_id": item.call_id,
            "name": item.name,
            "arguments": item.arguments,
        }

    if item_type == "message":
        return {
            "type": "message",
            "role": getattr(item, "role", "assistant"),
            "content": [
                {"type": "output_text", "text": c.text}
                for c in item.content
                if getattr(c, "type", None) == "output_text"
            ],
        }

    # Fallback for any other item type: dump and strip known output-only keys.
    dumped = item.model_dump() if hasattr(item, "model_dump") else dict(item)
    for k in ("id", "status", "parsed_arguments"):
        dumped.pop(k, None)
    return dumped


def _output_items_to_input(output: List[Any]) -> List[Dict]:
    return [_output_item_to_input(item) for item in output]


def _status_error(response: Any) -> Optional[str]:
    status = getattr(response, "status", None)
    if status in ("failed", "cancelled"):
        return f"OpenAI response {status}: {getattr(response, 'error', None)}"
    return None


_HISTORY_MARKER = "\n[Câu hỏi hiện tại]\n"

# Chỉ match khi từ "tiktok"/"youtube" xuất hiện như một từ riêng (word
# boundary) — tránh match nhầm trong domain khác hoặc chuỗi con bất kỳ.
_TIKTOK_PATTERN  = re.compile(r"\btiktok\b", re.IGNORECASE)
_YOUTUBE_PATTERN = re.compile(r"\byoutube\b", re.IGNORECASE)


def _current_question(task: str) -> str:
    """Lấy phần câu hỏi MỚI NHẤT từ task — nếu task có kèm lịch sử chat,
    không được detect platform dựa trên các lượt cũ (vd: lượt trước nhắc
    TikTok nhưng lượt này hỏi tiếp không liên quan platform nào)."""
    if _HISTORY_MARKER in task:
        return task.split(_HISTORY_MARKER)[-1]
    return task


def _detect_platform(task: str) -> Optional[str]:
    """Phát hiện platform user CHỈ ĐỊNH RÕ trong câu hỏi hiện tại.
    Trả về "tiktok"/"youtube" nếu chỉ một platform được nhắc, None nếu
    cả hai hoặc không platform nào được nhắc (để model tự quyết theo
    AGENT_SYSTEM bước 2)."""
    q = _current_question(task)
    has_tiktok = bool(_TIKTOK_PATTERN.search(q))
    has_youtube = bool(_YOUTUBE_PATTERN.search(q))
    if has_tiktok and not has_youtube:
        return "tiktok"
    if has_youtube and not has_tiktok:
        return "youtube"
    return None


def _filter_tools_by_platform(tools: List[Dict], task: str) -> List[Dict]:
    """Khoá cứng tool-set theo platform user nêu rõ. Đây là chặn ở tầng
    code, không phụ thuộc việc tool-model (gpt-4o-mini) có tuân thủ rule
    'chỉ dùng nền tảng được nêu rõ' trong AGENT_SYSTEM hay không — model
    không có khả năng gọi tool của platform kia vì nó không còn trong
    danh sách tools được truyền vào API nữa."""
    platform = _detect_platform(task)
    if platform is None:
        return tools

    blocked_prefix = "tiktok_" if platform == "youtube" else "youtube_"
    filtered = [t for t in tools if not t.get("name", "").startswith(blocked_prefix)]

    if len(filtered) != len(tools):
        logger.info(
            "Platform '%s' detected in task -> blocking '%s*' tools (%d/%d tools kept)",
            platform, blocked_prefix, len(filtered), len(tools),
        )
    return filtered


async def _execute_tools_parallel(
    output: List[Any],
    session_id: str,
    task: str,
    iteration: int,
) -> Tuple[List[Dict], List[Dict]]:
    """Execute all function_call items in parallel. Returns (function_call_outputs, tool_call_log_entries)."""
    call_items = _extract_function_calls(output)
    if not call_items:
        return [], []

    logger.info("Executing %d tool(s) in parallel: %s", len(call_items), [c.name for c in call_items])

    async def _run(item: Any) -> Tuple[Any, Dict, Any]:
        try:
            args = json.loads(item.arguments) if item.arguments else {}
        except json.JSONDecodeError:
            logger.error("Failed to parse tool arguments for %s: %r", item.name, item.arguments)
            args = {}
        result = await execute_tool(item.name, args)
        await log_tool_call(session_id, task, item.name, args, result, iteration)
        return item, args, result

    triples = await asyncio.gather(*[_run(c) for c in call_items])

    function_call_outputs = []
    log_entries = []
    for item, args, result in triples:
        log_entries.append({"tool": item.name, "inputs": args, "result": result})
        function_call_outputs.append({
            "type":    "function_call_output",
            "call_id": item.call_id,
            "output":  _serialize_result(result),
        })
    return function_call_outputs, log_entries


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
    # OpenAI's Responses API takes a plain list of input items (no Anthropic
    # content-block wrapping) and auto-caches repeated prefixes server-side,
    # so no explicit cache_control hint is needed for `instructions`.
    input_items: List[Dict] = [{"role": "user", "content": task}]
    tool_call_log: List[Dict] = []
    has_history = "\n[Câu hỏi hiện tại]\n" in task

    for iteration in range(1, max_iter + 1):
        logger.info("Agent iteration %d/%d model=%s", iteration, max_iter, _tool_model())

        force_tool = iteration == 1 and not tool_call_log and not has_history
        tool_choice = "required" if force_tool else "auto"

        response = await get_openai_client().responses.create(
            model=_tool_model(),
            max_output_tokens=_tool_max_tokens(),
            instructions=system,
            tools=tools,
            tool_choice=tool_choice,
            input=input_items,
        )

        err = _status_error(response)
        if err:
            raise RuntimeError(err)

        if _is_incomplete_for("max_output_tokens", response):
            if _dual_mode() and tool_call_log:
                logger.warning("max_output_tokens hit at iteration %d (dual mode) — falling through to synthesis model", iteration)
                input_items.extend(_output_items_to_input(response.output))
                synth = await get_openai_client().responses.create(
                    model=_synth_model(),
                    max_output_tokens=_synth_max_tokens(),
                    instructions=system,
                    input=input_items,
                )
                final_text = _extract_text(synth)
                enriched = await enrich_agent_result(final_text, tool_call_log, iteration)
                await log_agent_run(session_id, task, iteration, tool_call_log, final_text,
                    enriched["data"].get("sources", []), enriched["data"].get("videos", []),
                    enriched["data"].get("reviews_analyzed", 0))
                return enriched
            partial = _extract_text(response)
            if partial:
                return await enrich_agent_result(partial, tool_call_log, iteration)
            raise RuntimeError(f"Model hit max_output_tokens at iteration {iteration} without text.")

        call_items = _extract_function_calls(response.output)
        if call_items:
            input_items.extend(_output_items_to_input(response.output))
            function_call_outputs, log_entries = await _execute_tools_parallel(
                response.output, session_id, task, iteration
            )
            tool_call_log.extend(log_entries)
            input_items.extend(function_call_outputs)
            continue

        # status == "completed" and no function calls -> model is done.
        if _dual_mode() and tool_call_log:
            logger.info("Synthesis pass model=%s max_tokens=%d", _synth_model(), _synth_max_tokens())
            input_items.extend(_output_items_to_input(response.output))
            synth = await get_openai_client().responses.create(
                model=_synth_model(),
                max_output_tokens=_synth_max_tokens(),
                instructions=system,
                input=input_items,
            )
            err = _status_error(synth)
            if err:
                raise RuntimeError(err)
            final_text = _extract_text(synth)
        else:
            final_text = _extract_text(response)

        enriched = await enrich_agent_result(final_text, tool_call_log, iteration)
        await log_agent_run(
            session_id, task, iteration, tool_call_log, final_text,
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
    session_id = str(uuid.uuid4())
    input_items: List[Dict] = [{"role": "user", "content": task}]
    tool_call_log: List[Dict] = []
    has_history = "\n[Câu hỏi hiện tại]\n" in task

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
            # In dual-mode: don't stream the tool model's text — only the
            # synthesis model's final answer gets streamed.
            # In single-mode: stream text deltas normally.
            async for event in stream:
                if not _dual_mode() and event.type == "response.output_text.delta":
                    yield _sse({"type": "text_delta", "delta": event.delta})

            final = await stream.get_final_response()

        err = _status_error(final)
        if err:
            yield _sse({"type": "error", "message": err})
            return

        if _is_incomplete_for("max_output_tokens", final):
            if _dual_mode() and tool_call_log:
                logger.warning("max_output_tokens hit at iteration %d (dual mode) — falling through to synthesis model", iteration)
                input_items.extend(_output_items_to_input(final.output))
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
                enriched = await enrich_agent_result(synth_text, tool_call_log, iteration)
                yield _sse({"type": "done", "data": enriched["data"], "tool_calls": enriched["tool_calls"]})
                return
            partial = _extract_text(final)
            if partial:
                logger.warning("max_output_tokens hit at iteration %d — returning partial text", iteration)
                enriched = await enrich_agent_result(partial, tool_call_log, iteration)
                yield _sse({"type": "done", "data": enriched["data"], "tool_calls": enriched["tool_calls"]})
                return
            yield _sse({"type": "error", "message": "max_output_tokens reached without output — try increasing OPENAI_MAX_TOKENS"})
            return

        call_items = _extract_function_calls(final.output)
        if call_items:
            input_items.extend(_output_items_to_input(final.output))
            tool_names = [c.name for c in call_items]
            for name in tool_names:
                yield _sse({"type": "tool_start", "tool": name})
            function_call_outputs, log_entries = await _execute_tools_parallel(
                final.output, session_id, task, iteration
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

            input_items.extend(function_call_outputs)
            continue

        # status == "completed" and no function calls -> model is done.
        if _dual_mode() and tool_call_log:
            logger.info("Synthesis stream model=%s max_tokens=%d", _synth_model(), _synth_max_tokens())
            input_items.extend(_output_items_to_input(final.output))
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
            logger.info("Synthesis done status=%s chars=%d", final_synth.status, len(synth_text))
        else:
            collected_text = _extract_text(final)

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

    yield _sse({"type": "error", "message": f"Agent did not finish within {max_iter} iterations"})