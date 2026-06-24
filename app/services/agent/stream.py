from __future__ import annotations

import json
import uuid
from typing import AsyncGenerator, Dict, List, Optional

import app.services.prompts as _prompts
from app.config.logger import Logger
from app.services.agent import config
from app.services.agent.constants import HISTORY_MARKER
from app.services.agent.finalize import finish
from app.services.agent.platform import filter_tools_by_platform
from app.services.agent.synthesis import iter_synthesis_deltas
from app.services.agent.tools import execute_parallel, extract_function_calls
from app.utils.openai_client import get_openai_client
from app.utils.openai_responses import (
    extract_response_text,
    is_incomplete_for,
    output_items_to_input,
    status_error,
)

logger = Logger.get(__name__)


def _sse(data: Dict) -> str:
    """Định dạng một event Server-Sent Events."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def run_agent_stream(
    task: str,
    tools: List[Dict],
    max_iter: int = 10,
    system: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Chạy agent streaming — yield SSE events."""
    system = system or _prompts.AGENT_SYSTEM
    tools = filter_tools_by_platform(tools, task)

    session_id = str(uuid.uuid4())
    input_items: List[Dict] = [{"role": "user", "content": task}]
    tool_call_log: List[Dict] = []
    has_history = HISTORY_MARKER in task

    for iteration in range(1, max_iter + 1):
        force_tool = iteration == 1 and not tool_call_log and not has_history

        async with get_openai_client().responses.stream(
            model=config.tool_model(),
            max_output_tokens=config.tool_max_tokens(),
            instructions=system,
            tools=tools,
            tool_choice="required" if force_tool else "auto",
            input=input_items,
        ) as stream:
            async for event in stream:
                if not config.dual_mode() and event.type == "response.output_text.delta":
                    yield _sse({"type": "text_delta", "delta": event.delta})
            final = await stream.get_final_response()

        err = status_error(final)
        if err:
            yield _sse({"type": "error", "message": err})
            return

        if is_incomplete_for("max_output_tokens", final):
            async for chunk in _handle_incomplete_stream(
                final, system, input_items, task, iteration, tool_call_log,
            ):
                yield chunk
            return

        call_items = extract_function_calls(final.output)
        if call_items:
            input_items.extend(output_items_to_input(final.output))
            tool_names = [c.name for c in call_items]
            for name in tool_names:
                yield _sse({"type": "tool_start", "tool": name})

            outputs, entries = await execute_parallel(final.output, session_id, task, iteration)
            tool_call_log.extend(entries)

            for name in tool_names:
                yield _sse({"type": "tool_done", "tool": name})

            preview = _video_preview(tool_call_log)
            if preview:
                yield _sse({"type": "data_preview", "videos": preview})

            input_items.extend(outputs)
            continue

        collected = await _collect_final_text_stream(final, system, input_items, tool_call_log)
        async for chunk in _yield_text_deltas(collected.deltas):
            yield chunk

        enriched = await finish(
            session_id=session_id, task=task, iteration=iteration,
            tool_call_log=tool_call_log, final_text=collected.text,
        )
        yield _sse({"type": "done", "data": enriched["data"], "tool_calls": enriched["tool_calls"]})
        return

    yield _sse({"type": "error", "message": f"Agent did not finish within {max_iter} iterations"})


class _CollectedText:
    """Kết quả stream: full text + các delta đã emit."""

    def __init__(self, text: str, deltas: List[str]):
        """Lưu text đầy đủ và các delta đã stream."""
        self.text = text
        self.deltas = deltas


async def _collect_final_text_stream(final, system, input_items, tool_call_log) -> _CollectedText:
    """Thu thập câu trả lời cuối; dual-mode thì stream qua model tổng hợp."""
    if config.dual_mode() and tool_call_log:
        logger.info("[agent] synthesis_stream model=%s", config.synth_model())
        input_items.extend(output_items_to_input(final.output))
        text, deltas = "", []
        async for delta in iter_synthesis_deltas(system=system, input_items=input_items):
            text += delta
            deltas.append(delta)
        return _CollectedText(text, deltas)

    text = extract_response_text(final)
    return _CollectedText(text, [])


async def _yield_text_deltas(deltas: List[str]) -> AsyncGenerator[str, None]:
    """Gửi từng đoạn text qua SSE (model tool đã stream trực tiếp nếu không dual-mode)."""
    for delta in deltas:
        if delta:
            yield _sse({"type": "text_delta", "delta": delta})


def _video_preview(tool_call_log: List[Dict]) -> List[Dict]:
    """Lấy tối đa 10 video unique từ kết quả tool để preview UI."""
    seen: set = set()
    preview: List[Dict] = []
    for entry in tool_call_log:
        for video in (entry.get("result") or {}).get("videos") or []:
            vid = video.get("video_id") if isinstance(video, dict) else None
            if vid and vid not in seen:
                seen.add(vid)
                preview.append(video)
                if len(preview) >= 10:
                    return preview
    return preview


async def _handle_incomplete_stream(final, system, input_items, task, iteration, tool_call_log):
    """Gửi sự kiện SSE khi model hết token giữa chừng."""
    if config.dual_mode() and tool_call_log:
        logger.warning("[agent] max_output_tokens iteration=%d mode=dual_synthesis_stream", iteration)
        input_items.extend(output_items_to_input(final.output))
        synth_text = ""
        async for delta in iter_synthesis_deltas(system=system, input_items=input_items):
            synth_text += delta
            yield _sse({"type": "text_delta", "delta": delta})
        enriched = await enrich_stream_result(synth_text, tool_call_log, iteration, task)
        yield _sse({"type": "done", "data": enriched["data"], "tool_calls": enriched["tool_calls"]})
        return

    partial = extract_response_text(final)
    if partial:
        logger.warning("[agent] max_output_tokens iteration=%d partial=true", iteration)
        enriched = await enrich_stream_result(partial, tool_call_log, iteration, task)
        yield _sse({"type": "done", "data": enriched["data"], "tool_calls": enriched["tool_calls"]})
        return

    yield _sse({
        "type": "error",
        "message": "max_output_tokens reached without output — try increasing OPENAI_MAX_TOKENS",
    })


async def enrich_stream_result(text, tool_call_log, iteration, task):
    """Enrich kết quả stream (không ghi Mongo ở nhánh incomplete)."""
    from app.services.enricher import enrich_agent_result
    return await enrich_agent_result(text, tool_call_log, iteration, task=task)