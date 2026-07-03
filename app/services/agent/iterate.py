from collections.abc import AsyncGenerator

from app.ai.router import TASK_AGENT_TOOL
from app.config.logger import Logger
from app.exceptions import AiLayerConfigError, AiLayerError
from app.services.agent import config
from app.services.agent.engine import tool_round_action
from app.services.agent.events import (
    AgentEvent,
    data_preview as ev_data_preview,
    done as ev_done,
    error as ev_error,
    status as ev_status,
    text_delta as ev_text_delta,
    tool_done as ev_tool_done,
    tool_start as ev_tool_start,
)
from app.services.agent.loop import (
    begin_tool_round,
    bootstrap_agent,
    complete_tool_round,
    finish_agent,
    is_max_tokens_incomplete,
    video_preview,
)
from app.services.agent.synthesis import iter_synthesis_deltas, run_synthesis
from app.services.agent.tool_status import _parse_args, tool_status
from app.utils.llm_errors import log_error, user_message
from app.utils.llm_responses import create_response, extract_response_text, response_stream, status_error

logger = Logger.get(__name__)


async def _yield_synthesis(
    ctx: dict, *, forced: bool, stream_llm: bool
) -> AsyncGenerator[AgentEvent, None]:
    if not ctx["tool_call_log"]:
        return
    if stream_llm:
        detail_vi = (
            "Đang tổng hợp câu trả lời từ dữ liệu đã thu…"
            if forced
            else "Đang viết câu trả lời từ dữ liệu đã thu…"
        )
        detail_en = (
            "Summarizing answer from collected data…"
            if forced
            else "Writing answer from collected data…"
        )
        logger.info("[agent] synthesis_stream model=%s (forced=%s)", config.synth_model(), forced)
        yield ev_status(detail_vi, detail_en)
        collected_text = ""
        async for delta in iter_synthesis_deltas(
            system=ctx["system"],
            task=ctx["task"],
            tool_call_log=ctx["tool_call_log"],
        ):
            if delta:
                collected_text += delta
                yield ev_text_delta(delta)
    else:
        collected_text = await run_synthesis(
            system=ctx["system"],
            task=ctx["task"],
            tool_call_log=ctx["tool_call_log"],
        )
    enriched = await finish_agent(ctx, iteration=ctx.get("_iteration", 1), final_text=collected_text)
    yield ev_done(enriched)


async def _handle_incomplete(
    ctx: dict,
    final,
    iteration: int,
    text_streamed: bool,
    *,
    stream_llm: bool,
) -> AsyncGenerator[AgentEvent, None]:
    if config.dual_mode() and ctx["tool_call_log"]:
        logger.warning("[agent] max_output_tokens iteration=%d mode=dual_synthesis_stream", iteration)
        if stream_llm:
            synth_text = ""
            async for delta in iter_synthesis_deltas(
                system=ctx["system"],
                task=ctx["task"],
                tool_call_log=ctx["tool_call_log"],
            ):
                synth_text += delta
                if delta:
                    yield ev_text_delta(delta)
            enriched = await finish_agent(ctx, iteration=iteration, final_text=synth_text)
            yield ev_done(enriched)
            return
        final_text = await run_synthesis(
            system=ctx["system"],
            task=ctx["task"],
            tool_call_log=ctx["tool_call_log"],
        )
        enriched = await finish_agent(ctx, iteration=iteration, final_text=final_text)
        yield ev_done(enriched)
        return

    partial = extract_response_text(final)
    if partial:
        logger.warning("[agent] max_output_tokens iteration=%d partial=true", iteration)
        if stream_llm and not text_streamed:
            yield ev_text_delta(partial)
        enriched = await finish_agent(ctx, iteration=iteration, final_text=partial)
        yield ev_done(enriched)
        return

    yield ev_error("max_output_tokens reached without output — tăng max_tokens trên Supabase AI_MODELS")


async def run_agent_events(
    task: str,
    tools: list[dict],
    max_iter: int = 10,
    system: str | None = None,
    *,
    stream_llm: bool = False,
) -> AsyncGenerator[AgentEvent, None]:
    """Unified agent loop — runner consumes final `done`; stream maps all events to SSE."""
    try:
        ctx = await bootstrap_agent(task, tools, system, max_iter)
    except AiLayerConfigError as exc:
        yield ev_error(exc.message)
        return
    except AiLayerError as exc:
        yield ev_error(exc.message)
        return

    for iteration in range(1, ctx["max_iter"] + 1):
        ctx["_iteration"] = iteration
        text_streamed = False

        if stream_llm and iteration == 1 and (not ctx["tool_call_log"]):
            yield ev_status("Đang phân tích câu hỏi…", "Analyzing your question…")

        if not stream_llm:
            logger.info("[agent] iteration=%d/%d model=%s", iteration, ctx["max_iter"], config.tool_model())

        try:
            if stream_llm:
                llm_kwargs = {
                    "task": TASK_AGENT_TOOL,
                    "model": config.tool_model(),
                    "max_output_tokens": config.tool_max_tokens(),
                    "instructions": ctx["system"],
                    "tools": ctx["tools"],
                    "tool_choice": "auto",
                    "input": ctx["input_items"],
                }
                final = None
                async with response_stream(**llm_kwargs) as stream:
                    async for event in stream:
                        if event.type != "response.output_text.delta" or not event.delta:
                            continue
                        if config.dual_mode() and ctx["tool_call_log"]:
                            continue
                        text_streamed = True
                        yield ev_text_delta(event.delta)
                    final = await stream.get_final_response()
            else:
                final = await create_response(
                    task=TASK_AGENT_TOOL,
                    model=config.tool_model(),
                    max_output_tokens=config.tool_max_tokens(),
                    instructions=ctx["system"],
                    tools=ctx["tools"],
                    tool_choice="auto",
                    input=ctx["input_items"],
                )
        except Exception as exc:
            where = f"agent_stream iter={iteration}" if stream_llm else f"agent iter={iteration}"
            log_error(logger, exc, where=where)
            yield ev_error(user_message(exc))
            return

        err = status_error(final)
        if err:
            yield ev_error(err)
            return

        if is_max_tokens_incomplete(final):
            async for event in _handle_incomplete(ctx, final, iteration, text_streamed, stream_llm=stream_llm):
                yield event
            return

        call_items = await begin_tool_round(ctx, final.output)
        if call_items:
            for call in call_items:
                args = _parse_args(getattr(call, "arguments", None))
                vi, en = tool_status(call.name, args)
                yield ev_tool_start(call.name, vi, en)
            await complete_tool_round(ctx, final.output, iteration)
            for call in call_items:
                yield ev_tool_done(call.name)
            preview = video_preview(ctx["tool_call_log"])
            if preview:
                yield ev_data_preview(preview)
            if tool_round_action(ctx, iteration) == "force_synthesis":
                async for event in _yield_synthesis(ctx, forced=True, stream_llm=stream_llm):
                    yield event
                return
            continue

        if config.dual_mode() and ctx["tool_call_log"]:
            async for event in _yield_synthesis(ctx, forced=False, stream_llm=stream_llm):
                yield event
            return

        collected_text = extract_response_text(final)
        if stream_llm and not text_streamed and collected_text:
            yield ev_text_delta(collected_text)
        enriched = await finish_agent(ctx, iteration=iteration, final_text=collected_text)
        yield ev_done(enriched)
        return

    if ctx["tool_call_log"]:
        async for event in _yield_synthesis(ctx, forced=True, stream_llm=stream_llm):
            yield event
        return

    yield ev_error(f"Agent did not finish within {ctx['max_iter']} iterations")
