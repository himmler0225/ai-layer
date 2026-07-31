from collections.abc import AsyncGenerator
from typing import Any

from app.ai.router import TASK_AGENT_TOOL
from app.config.logger import Logger
from app.exceptions import AiLayerError
from app.services.agent import config
from app.services.agent.core.engine import tool_round_action
from app.services.agent.guards.fallback import catalog_fallback_call, catalog_forced_tool_choice
from app.services.agent.events import (
    AgentEvent,
    data_preview as ev_data_preview,
    done as ev_done,
    error as ev_error,
    error_key as ev_error_key,
    status as ev_status,
    text_delta as ev_text_delta,
    tool_done as ev_tool_done,
    tool_start as ev_tool_start,
    tool_status,
    _parse_args,
)
from app.services.agent.core.context import (
    begin_tool_round,
    bootstrap_agent,
    complete_tool_round,
    finish_agent,
    is_max_tokens_incomplete,
    video_preview,
)
from app.services.agent.synthesis import iter_synthesis_deltas, run_synthesis
from app.i18n import both, t
from app.utils.llm_errors import log_error, user_message
from app.utils.llm_responses import create_response, extract_response_text, response_stream, status_error

logger = Logger.get(__name__)


async def _yield_synthesis(
    ctx: dict, *, forced: bool, stream_llm: bool
) -> AsyncGenerator[AgentEvent, None]:
    """(Nội bộ) Yield synthesis (async) `_yield_synthesis`.

    Args:
        ctx: (dict) Tham số `ctx`.
        forced: (bool) Tham số `forced`.
        stream_llm: (bool) Tham số `stream_llm`.

    Returns:
        (AsyncGenerator[AgentEvent, None]) Kết quả trả về."""
    if not ctx["tool_call_log"]:
        return
    if stream_llm:
        detail_vi, detail_en = both("agent.status.synthesizing" if forced else "agent.status.writing")
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
    """(Nội bộ) Xử lý incomplete (async) `_handle_incomplete`.

    Args:
        ctx: (dict) Tham số `ctx`.
        final: (Any) Tham số `final`.
        iteration: (int) Tham số `iteration`.
        text_streamed: (bool) Tham số `text_streamed`.
        stream_llm: (bool) Tham số `stream_llm`.

    Returns:
        (AsyncGenerator[AgentEvent, None]) Kết quả trả về."""
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

    yield ev_error_key("errors.max_output_tokens")


async def _invoke_llm(
    ctx: dict,
    *,
    stream_llm: bool,
    tool_choice: str,
    iteration: int,
) -> tuple[Any, bool]:
    """Gọi LLM tool round; trả về (response, text_streamed)."""
    text_streamed = False
    if stream_llm:
        llm_kwargs = {
            "task": TASK_AGENT_TOOL,
            "model": config.tool_model(),
            "max_output_tokens": config.tool_max_tokens(),
            "instructions": ctx["system"],
            "tools": ctx["tools"],
            "tool_choice": tool_choice,
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
            final = await stream.get_final_response()
        return final, text_streamed

    if not stream_llm:
        logger.info(
            "[agent] iteration=%d/%d model=%s tool_choice=%s",
            iteration,
            ctx["max_iter"],
            config.tool_model(),
            tool_choice,
        )
    final = await create_response(
        task=TASK_AGENT_TOOL,
        model=config.tool_model(),
        max_output_tokens=config.tool_max_tokens(),
        instructions=ctx["system"],
        tools=ctx["tools"],
        tool_choice=tool_choice,
        input=ctx["input_items"],
    )
    return final, text_streamed


def _log_llm_round(final: Any, *, iteration: int, attempt: int, tool_choice: Any) -> None:
    """(Nội bộ) Log llm round `_log_llm_round`.

    Args:
        final: (Any) Tham số `final`.
        iteration: (int) Tham số `iteration`.
        attempt: (int) Tham số `attempt`.
        tool_choice: (Any) Tham số `tool_choice`.

    Returns:
        (None) Kết quả trả về."""
    output = getattr(final, "output", None) or []
    names = [getattr(item, "name", None) for item in output if getattr(item, "type", None) == "function_call"]
    logger.info(
        "[agent] llm iter=%d attempt=%d tool_choice=%s output_items=%d tool_calls=%s text_len=%d",
        iteration,
        attempt,
        tool_choice,
        len(output),
        names,
        len(extract_response_text(final)),
    )


def _should_retry_empty_tool_round(
    ctx: dict,
    *,
    iteration: int,
    call_items: list,
    collected_text: str,
) -> bool:
    """(Nội bộ) Should retry empty tool round `_should_retry_empty_tool_round`.

    Args:
        ctx: (dict) Tham số `ctx`.
        iteration: (int) Tham số `iteration`.
        call_items: (list) Tham số `call_items`.
        collected_text: (str) Tham số `collected_text`.

    Returns:
        (bool) Kết quả trả về."""
    if iteration != 1 or ctx["tool_call_log"]:
        return False
    if call_items or collected_text.strip():
        return False
    return bool(ctx["tools"])


def _resolve_empty_tool_round(
    ctx: dict,
    *,
    iteration: int,
    attempt: int,
    call_items: list,
    collected_text: str,
    tool_choice: Any,
) -> Any:
    """Return next tool_choice for retry, or None to stop retrying."""
    if not _should_retry_empty_tool_round(
        ctx, iteration=iteration, call_items=call_items, collected_text=collected_text
    ):
        return None
    if attempt >= 2:
        return None
    if attempt == 0:
        forced = catalog_forced_tool_choice(ctx["task"], ctx["tools"])
        if forced:
            logger.warning(
                "[agent] empty tool round iter=1, retrying forced tool=%s",
                forced.get("function", {}).get("name"),
            )
            return forced
    logger.warning(
        "[agent] empty tool round iter=1, retrying tool_choice=required tools=%d",
        len(ctx["tools"]),
    )
    return "required"


def _error_from_ai_layer(exc: AiLayerError) -> AgentEvent:
    """(Nội bộ) Error from ai layer `_error_from_ai_layer`.

    Args:
        exc: (AiLayerError) Tham số `exc`.

    Returns:
        (AgentEvent) Kết quả trả về."""
    if exc.message_key:
        return ev_error_key(exc.message_key, **exc.message_params)
    if exc.message_en:
        return ev_error(exc.message, exc.message_en)
    return ev_error(exc.message, exc.message)


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
    except AiLayerError as exc:
        yield _error_from_ai_layer(exc)
        return

    for iteration in range(1, ctx["max_iter"] + 1):
        ctx["_iteration"] = iteration
        text_streamed = False

        if stream_llm and iteration == 1 and (not ctx["tool_call_log"]):
            yield ev_status(*both("agent.status.analyzing"))

        tool_choice: Any = "auto"
        final = None
        text_streamed = False
        call_items: list = []

        for attempt in range(3):
            try:
                if stream_llm:
                    llm_kwargs = {
                        "task": TASK_AGENT_TOOL,
                        "model": config.tool_model(),
                        "max_output_tokens": config.tool_max_tokens(),
                        "instructions": ctx["system"],
                        "tools": ctx["tools"],
                        "tool_choice": tool_choice,
                        "input": ctx["input_items"],
                    }
                    final = None
                    text_streamed = False
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
                    final, text_streamed = await _invoke_llm(
                        ctx, stream_llm=False, tool_choice=tool_choice, iteration=iteration
                    )
            except Exception as exc:
                where = f"agent_stream iter={iteration}" if stream_llm else f"agent iter={iteration}"
                log_error(logger, exc, where=where)
                vi, en = user_message(exc)
                yield ev_error(vi, en)
                return

            err = status_error(final)
            if err:
                yield ev_error(t("llm.raw", "vi", detail=err, tag=""), t("llm.raw", "en", detail=err, tag=""))
                return

            if is_max_tokens_incomplete(final):
                async for event in _handle_incomplete(ctx, final, iteration, text_streamed, stream_llm=stream_llm):
                    yield event
                return

            call_items = await begin_tool_round(ctx, final.output)
            _log_llm_round(final, iteration=iteration, attempt=attempt, tool_choice=tool_choice)
            if call_items:
                break

            collected_text = extract_response_text(final)
            next_choice = _resolve_empty_tool_round(
                ctx,
                iteration=iteration,
                attempt=attempt,
                call_items=call_items,
                collected_text=collected_text,
                tool_choice=tool_choice,
            )
            if next_choice is not None:
                if stream_llm:
                    yield ev_status(*both("agent.status.calling_tools"))
                tool_choice = next_choice
                continue
            break

        used_fallback = False
        if not call_items:
            fallback = catalog_fallback_call(ctx["task"], ctx["tools"])
            if fallback:
                logger.warning("[agent] catalog fallback execute tool=%s", fallback.name)
                call_items = await begin_tool_round(ctx, [fallback])
                used_fallback = True

        if call_items:
            round_output = list(call_items)
            for call in call_items:
                args = _parse_args(getattr(call, "arguments", None))
                vi, en = tool_status(call.name, args)
                yield ev_tool_start(call.name, vi, en, args=args)
            await complete_tool_round(ctx, round_output, iteration)
            for call in call_items:
                yield ev_tool_done(call.name)
            preview = video_preview(ctx["tool_call_log"])
            if preview:
                yield ev_data_preview(preview)
            # Fallback nghĩa là vòng này model không gọi tool thật — text (nếu có)
            # đã stream ra client rồi nhưng không phải câu trả lời cuối, nên ép
            # synthesis ngay thay vì cho model thêm 1 vòng dễ lặp lại y hệt.
            if used_fallback or tool_round_action(ctx, iteration) == "force_synthesis":
                async for event in _yield_synthesis(ctx, forced=True, stream_llm=stream_llm):
                    yield event
                return
            continue

        if config.dual_mode() and ctx["tool_call_log"]:
            async for event in _yield_synthesis(ctx, forced=False, stream_llm=stream_llm):
                yield event
            return

        collected_text = extract_response_text(final)
        if not collected_text.strip() and not ctx["tool_call_log"] and ctx["tools"]:
            logger.warning("[agent] finished without tools or text iter=%d", iteration)
            yield ev_error_key("errors.agent_no_tool")
            return
        if stream_llm and not text_streamed and collected_text:
            yield ev_text_delta(collected_text)
        enriched = await finish_agent(ctx, iteration=iteration, final_text=collected_text)
        yield ev_done(enriched)
        return

    if ctx["tool_call_log"]:
        async for event in _yield_synthesis(ctx, forced=True, stream_llm=stream_llm):
            yield event
        return

    yield ev_error_key("errors.agent_max_iterations", max_iter=ctx["max_iter"])
