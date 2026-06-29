from __future__ import annotations
import uuid
from typing import Any, Dict, List, Optional
from app.services.agent import config
from app.services.agent.finalize import finish
from app.services.agent.platform import prepare_tools_for_task
from app.services.agent.synthesis import run_synthesis
from app.services.agent.tools import execute_parallel, extract_function_calls
from app.utils.openai_responses import extract_response_text, is_incomplete_for, output_items_to_input

def new_context(*, task: str, tools: List[Dict], system: str, max_iter: int) -> Dict[str, Any]:
    return {'session_id': str(uuid.uuid4()), 'task': task, 'system': system, 'tools': tools, 'max_iter': max_iter, 'input_items': [{'role': 'user', 'content': task}], 'tool_call_log': []}

async def bootstrap_agent(task: str, tools: List[Dict], system: Optional[str], max_iter: int) -> Dict[str, Any]:
    import app.services.prompts as _prompts
    resolved_system = system or _prompts.AGENT_SYSTEM
    if not (resolved_system or '').strip():
        raise ValueError('AGENT_SYSTEM chưa cấu hình — thêm key trên Supabase config')
    prepared = await prepare_tools_for_task(tools, task)
    return new_context(task=task, tools=prepared, system=resolved_system, max_iter=max_iter)

def extract_calls(output: Any) -> List[Any]:
    return extract_function_calls(output)

def is_max_tokens_incomplete(response: Any) -> bool:
    return is_incomplete_for('max_output_tokens', response)

async def begin_tool_round(ctx: Dict[str, Any], output: Any) -> List[Any]:
    call_items = extract_calls(output)
    if not call_items:
        return []
    ctx['input_items'].extend(output_items_to_input(output))
    return call_items

async def complete_tool_round(ctx: Dict[str, Any], output: Any, iteration: int) -> None:
    outputs, entries = await execute_parallel(output, ctx['session_id'], ctx['task'], iteration)
    ctx['tool_call_log'].extend(entries)
    ctx['input_items'].extend(outputs)

async def run_tool_round(ctx: Dict[str, Any], output: Any, iteration: int) -> List[Any]:
    call_items = await begin_tool_round(ctx, output)
    if not call_items:
        return []
    await complete_tool_round(ctx, output, iteration)
    return call_items

async def resolve_final_text(ctx: Dict[str, Any], response: Any) -> str:
    if config.dual_mode() and ctx['tool_call_log']:
        ctx['input_items'].extend(output_items_to_input(response.output))
        return await run_synthesis(system=ctx['system'], input_items=ctx['input_items'])
    return extract_response_text(response)

async def finish_agent(ctx: Dict[str, Any], *, iteration: int, final_text: str, include_summary: bool=True) -> Dict[str, Any]:
    return await finish(session_id=ctx['session_id'], task=ctx['task'], iteration=iteration, tool_call_log=ctx['tool_call_log'], final_text=final_text, include_summary=include_summary)

async def handle_incomplete_sync(ctx: Dict[str, Any], response: Any, iteration: int) -> Dict[str, Any]:
    if config.dual_mode() and ctx['tool_call_log']:
        ctx['input_items'].extend(output_items_to_input(response.output))
        final_text = await run_synthesis(system=ctx['system'], input_items=ctx['input_items'])
        return await finish_agent(ctx, iteration=iteration, final_text=final_text)
    partial = extract_response_text(response)
    if partial:
        return await finish_agent(ctx, iteration=iteration, final_text=partial)
    raise RuntimeError(f'Model hit max_output_tokens at iteration {iteration} without text.')

def video_preview(tool_call_log: List[Dict]) -> List[Dict]:
    seen: set[str] = set()
    preview: List[Dict] = []
    for entry in tool_call_log:
        for video in (entry.get('result') or {}).get('videos') or []:
            vid = video.get('video_id') if isinstance(video, dict) else None
            if vid and vid not in seen:
                seen.add(vid)
                preview.append(video)
                if len(preview) >= 10:
                    return preview
    return preview
