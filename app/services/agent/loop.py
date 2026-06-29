from __future__ import annotations
import uuid
from typing import Any, Dict, List, Optional
from app.services.agent import config
from app.services.agent.finalize import finish
from app.services.agent.platform import prepare_tools_for_task
from app.services.agent.guards import apply_tool_budget, extract_video_items
from app.services.agent.synthesis import run_synthesis
from app.services.agent.tools import execute_parallel, extract_function_calls
from app.utils.openai_responses import extract_response_text, is_incomplete_for, output_items_to_input

def new_context(*, task: str, tools: List[Dict], system: str, max_iter: int) -> Dict[str, Any]:
    """New context.

    Args:
        task: (str) Tham số `task`.
        tools: (List[Dict]) Tham số `tools`.
        system: (str) Tham số `system`.
        max_iter: (int) Tham số `max_iter`.

    Returns:
        (Dict[str, Any]) Kết quả trả về."""
    return {'session_id': str(uuid.uuid4()), 'task': task, 'system': system, 'tools': tools, 'max_iter': max_iter, 'input_items': [{'role': 'user', 'content': task}], 'tool_call_log': []}

async def bootstrap_agent(task: str, tools: List[Dict], system: Optional[str], max_iter: int) -> Dict[str, Any]:
    """Khởi tạo agent (async).

    Args:
        task: (str) Tham số `task`.
        tools: (List[Dict]) Tham số `tools`.
        system: (Optional[str]) Tham số `system`.
        max_iter: (int) Tham số `max_iter`.

    Returns:
        (Dict[str, Any]) Kết quả trả về."""
    import app.services.prompts as _prompts
    resolved_system = system or _prompts.AGENT_SYSTEM
    if not (resolved_system or '').strip():
        raise ValueError('AGENT_SYSTEM chưa cấu hình — thêm key trên Supabase config')
    prepared = await prepare_tools_for_task(tools, task)
    return new_context(task=task, tools=prepared, system=resolved_system, max_iter=max_iter)

def extract_calls(output: Any) -> List[Any]:
    """Trích xuất calls.

    Args:
        output: (Any) Tham số `output`.

    Returns:
        (List[Any]) Kết quả trả về."""
    return extract_function_calls(output)

def is_max_tokens_incomplete(response: Any) -> bool:
    """Is max tokens incomplete.

    Args:
        response: (Any) Tham số `response`.

    Returns:
        (bool) Kết quả trả về."""
    return is_incomplete_for('max_output_tokens', response)

async def begin_tool_round(ctx: Dict[str, Any], output: Any) -> List[Any]:
    """Begin tool round (async).

    Args:
        ctx: (Dict[str, Any]) Tham số `ctx`.
        output: (Any) Tham số `output`.

    Returns:
        (List[Any]) Kết quả trả về."""
    call_items = extract_calls(output)
    if not call_items:
        return []
    ctx['input_items'].extend(output_items_to_input(output))
    return call_items

async def complete_tool_round(ctx: Dict[str, Any], output: Any, iteration: int) -> None:
    """Hoàn tất tool round (async).

    Args:
        ctx: (Dict[str, Any]) Tham số `ctx`.
        output: (Any) Tham số `output`.
        iteration: (int) Tham số `iteration`.

    Returns:
        (None) Kết quả trả về."""
    outputs, entries = await execute_parallel(
        output, ctx['session_id'], ctx['task'], iteration, tool_call_log=ctx['tool_call_log'],
    )
    ctx['tool_call_log'].extend(entries)
    ctx['input_items'].extend(outputs)
    apply_tool_budget(ctx)

async def run_tool_round(ctx: Dict[str, Any], output: Any, iteration: int) -> List[Any]:
    """Chạy tool round (async).

    Args:
        ctx: (Dict[str, Any]) Tham số `ctx`.
        output: (Any) Tham số `output`.
        iteration: (int) Tham số `iteration`.

    Returns:
        (List[Any]) Kết quả trả về."""
    call_items = await begin_tool_round(ctx, output)
    if not call_items:
        return []
    await complete_tool_round(ctx, output, iteration)
    return call_items

async def resolve_final_text(ctx: Dict[str, Any], response: Any) -> str:
    """Giải quyết final text (async).

    Args:
        ctx: (Dict[str, Any]) Tham số `ctx`.
        response: (Any) Tham số `response`.

    Returns:
        (str) Kết quả trả về."""
    if config.dual_mode() and ctx['tool_call_log']:
        return await run_synthesis(
            system=ctx['system'],
            task=ctx['task'],
            tool_call_log=ctx['tool_call_log'],
        )
    return extract_response_text(response)

async def finish_agent(ctx: Dict[str, Any], *, iteration: int, final_text: str, include_summary: bool | None = None) -> Dict[str, Any]:
    """Hoàn tất agent (async).

    Args:
        ctx: (Dict[str, Any]) Tham số `ctx`.
        iteration: (int) Tham số `iteration`.
        final_text: (str) Tham số `final_text`.
        include_summary: (bool | None) Override AGENT_INCLUDE_REVIEW_SUMMARY.

    Returns:
        (Dict[str, Any]) Kết quả trả về."""
    use_summary = config.include_review_summary() if include_summary is None else include_summary
    return await finish(
        session_id=ctx['session_id'],
        task=ctx['task'],
        iteration=iteration,
        tool_call_log=ctx['tool_call_log'],
        final_text=final_text,
        include_summary=use_summary,
    )

async def handle_incomplete_sync(ctx: Dict[str, Any], response: Any, iteration: int) -> Dict[str, Any]:
    """Xử lý incomplete sync (async).

    Args:
        ctx: (Dict[str, Any]) Tham số `ctx`.
        response: (Any) Tham số `response`.
        iteration: (int) Tham số `iteration`.

    Returns:
        (Dict[str, Any]) Kết quả trả về."""
    if config.dual_mode() and ctx['tool_call_log']:
        final_text = await run_synthesis(
            system=ctx['system'],
            task=ctx['task'],
            tool_call_log=ctx['tool_call_log'],
        )
        return await finish_agent(ctx, iteration=iteration, final_text=final_text)
    partial = extract_response_text(response)
    if partial:
        return await finish_agent(ctx, iteration=iteration, final_text=partial)
    raise RuntimeError(f'Model hit max_output_tokens at iteration {iteration} without text.')

def video_preview(tool_call_log: List[Dict]) -> List[Dict]:
    """Video preview.

    Args:
        tool_call_log: (List[Dict]) Tham số `tool_call_log`.

    Returns:
        (List[Dict]) Kết quả trả về."""
    seen: set[str] = set()
    preview: List[Dict] = []
    for entry in tool_call_log:
        for video in extract_video_items(entry.get('result')):
            vid = video.get('video_id') if isinstance(video, dict) else None
            if vid and vid not in seen:
                seen.add(vid)
                preview.append(video)
                if len(preview) >= 10:
                    return preview
    return preview
