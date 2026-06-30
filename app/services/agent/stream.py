from __future__ import annotations
import json
from typing import AsyncGenerator, Dict, List, Optional
from app.ai.router import TASK_AGENT_TOOL
from app.config.logger import Logger
from app.services.agent import config
from app.services.agent.engine import tool_round_action
from app.services.agent.loop import (
    begin_tool_round,
    bootstrap_agent,
    complete_tool_round,
    finish_agent,
    is_max_tokens_incomplete,
    video_preview,
)
from app.services.agent.synthesis import iter_synthesis_deltas
from app.exceptions import AiLayerConfigError, AiLayerError
from app.services.agent.tool_status import _parse_args, tool_status
from app.utils.llm_errors import log_error, user_message
from app.utils.llm_responses import extract_response_text, response_stream_with_retry, status_error
logger = Logger.get(__name__)

def _sse(data: Dict) -> str:
    return f'data: {json.dumps(data, ensure_ascii=False)}\n\n'

async def _emit_done(ctx: Dict, iteration: int, final_text: str) -> AsyncGenerator[str, None]:
    enriched = await finish_agent(ctx, iteration=iteration, final_text=final_text)
    yield _sse({'type': 'done', 'data': enriched['data'], 'tool_calls': enriched['tool_calls']})

async def _stream_synthesis(ctx: Dict, *, forced: bool = False) -> AsyncGenerator[str, None]:
    collected_text = ''
    if not ctx['tool_call_log']:
        return
    logger.info('[agent] synthesis_stream model=%s (forced=%s)', config.synth_model(), forced)
    yield _sse({
        'type': 'status',
        'detail_vi': 'Đang tổng hợp câu trả lời từ dữ liệu đã thu…',
        'detail_en': 'Summarizing answer from collected data…',
    })
    async for delta in iter_synthesis_deltas(
        system=ctx['system'],
        task=ctx['task'],
        tool_call_log=ctx['tool_call_log'],
    ):
        if delta:
            collected_text += delta
            yield _sse({'type': 'text_delta', 'delta': delta})
    async for chunk in _emit_done(ctx, ctx.get('_iteration', 1), collected_text):
        yield chunk

async def run_agent_stream(task: str, tools: List[Dict], max_iter: int=10, system: Optional[str]=None) -> AsyncGenerator[str, None]:
    """Chạy agent stream (async)."""
    try:
        ctx = await bootstrap_agent(task, tools, system, max_iter)
    except AiLayerConfigError as exc:
        yield _sse({'type': 'error', 'message': exc.message})
        return
    except AiLayerError as exc:
        yield _sse({'type': 'error', 'message': exc.message})
        return
    for iteration in range(1, ctx['max_iter'] + 1):
        ctx['_iteration'] = iteration
        text_streamed = False
        if iteration == 1 and (not ctx['tool_call_log']):
            yield _sse({'type': 'status', 'detail_vi': 'Đang phân tích câu hỏi…', 'detail_en': 'Analyzing your question…'})
        try:
            async with response_stream_with_retry(task=TASK_AGENT_TOOL, model=config.tool_model(), max_output_tokens=config.tool_max_tokens(), instructions=ctx['system'], tools=ctx['tools'], tool_choice='auto', input=ctx['input_items']) as stream:
                async for event in stream:
                    if event.type != 'response.output_text.delta' or not event.delta:
                        continue
                    if config.dual_mode() and ctx['tool_call_log']:
                        continue
                    text_streamed = True
                    yield _sse({'type': 'text_delta', 'delta': event.delta})
                final = await stream.get_final_response()
        except Exception as exc:
            log_error(logger, exc, where=f'agent_stream iter={iteration}')
            yield _sse({'type': 'error', 'message': user_message(exc)})
            return
        err = status_error(final)
        if err:
            yield _sse({'type': 'error', 'message': err})
            return
        if is_max_tokens_incomplete(final):
            async for chunk in _handle_incomplete_stream(ctx, final, iteration, text_streamed):
                yield chunk
            return
        call_items = await begin_tool_round(ctx, final.output)
        if call_items:
            for call in call_items:
                args = _parse_args(getattr(call, 'arguments', None))
                vi, en = tool_status(call.name, args)
                yield _sse({'type': 'tool_start', 'tool': call.name, 'detail_vi': vi, 'detail_en': en})
            await complete_tool_round(ctx, final.output, iteration)
            for call in call_items:
                yield _sse({'type': 'tool_done', 'tool': call.name})
            preview = video_preview(ctx['tool_call_log'])
            if preview:
                yield _sse({'type': 'data_preview', 'videos': preview})
            if tool_round_action(ctx, iteration) == 'force_synthesis':
                async for chunk in _stream_synthesis(ctx, forced=True):
                    yield chunk
                return
            continue
        collected_text = ''
        if config.dual_mode() and ctx['tool_call_log']:
            logger.info('[agent] synthesis_stream model=%s', config.synth_model())
            yield _sse({'type': 'status', 'detail_vi': 'Đang viết câu trả lời từ dữ liệu đã thu…', 'detail_en': 'Writing answer from collected data…'})
            async for delta in iter_synthesis_deltas(
                system=ctx['system'],
                task=ctx['task'],
                tool_call_log=ctx['tool_call_log'],
            ):
                if delta:
                    collected_text += delta
                    yield _sse({'type': 'text_delta', 'delta': delta})
        else:
            collected_text = extract_response_text(final)
            if not text_streamed and collected_text:
                yield _sse({'type': 'text_delta', 'delta': collected_text})
        async for chunk in _emit_done(ctx, iteration, collected_text):
            yield chunk
        return
    if ctx['tool_call_log']:
        async for chunk in _stream_synthesis(ctx, forced=True):
            yield chunk
        return
    yield _sse({'type': 'error', 'message': f"Agent did not finish within {ctx['max_iter']} iterations"})

async def _handle_incomplete_stream(ctx: Dict, final, iteration: int, text_streamed: bool) -> AsyncGenerator[str, None]:
    if config.dual_mode() and ctx['tool_call_log']:
        logger.warning('[agent] max_output_tokens iteration=%d mode=dual_synthesis_stream', iteration)
        synth_text = ''
        async for delta in iter_synthesis_deltas(
            system=ctx['system'],
            task=ctx['task'],
            tool_call_log=ctx['tool_call_log'],
        ):
            synth_text += delta
            if delta:
                yield _sse({'type': 'text_delta', 'delta': delta})
        async for chunk in _emit_done(ctx, iteration, synth_text):
            yield chunk
        return
    partial = extract_response_text(final)
    if partial:
        logger.warning('[agent] max_output_tokens iteration=%d partial=true', iteration)
        if not text_streamed:
            yield _sse({'type': 'text_delta', 'delta': partial})
        async for chunk in _emit_done(ctx, iteration, partial):
            yield chunk
        return
    yield _sse({'type': 'error', 'message': 'max_output_tokens reached without output — tăng max_tokens trên Supabase AI_MODELS'})
