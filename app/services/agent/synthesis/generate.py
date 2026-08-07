import json
from typing import Any
from collections.abc import AsyncGenerator

import app.config.settings as settings
import app.services.prompts as _prompts
from app.ai.router import TASK_AGENT_SYNTH
from app.config.logger import Logger, log_event
from app.services.agent import config
from app.services.agent.tooling import serialize_result
from app.exceptions import AiLayerLLMError
from app.utils.llm_errors import is_upstream_gateway_error, log_error, user_message
from app.utils.llm_responses import (
    create_response,
    extract_response_text,
    response_stream,
    status_error,
)

logger = Logger.get(__name__)

_DEFAULT_SYNTH_INPUT_CHARS = 28_000


def _synth_input_budget() -> int:
    """(Internal) Compute the max character budget for the synthesis input built from tool results.

    Returns:
        (int) 3x the configured AGENT_MAX_RESULT_CHARS (default 8000), clamped
        between 12,000 and _DEFAULT_SYNTH_INPUT_CHARS (28,000)."""
    base = getattr(settings, "AGENT_MAX_RESULT_CHARS", 8000) or 8000
    return min(max(base * 3, 12_000), _DEFAULT_SYNTH_INPUT_CHARS)


def models_with_fallback(primary: str, fallback: str | None = None) -> list[str]:
    """List of models to try in order: primary first, then a fallback (usually tool_model)."""
    fb = fallback or config.tool_model()
    if primary != fb:
        return [primary, fb]
    return [primary]


def synth_models_to_try() -> list[str]:
    """Build the ordered list of models to attempt for the synthesis round.

    Returns:
        (list[str]) The configured synth model, followed by the tool model as fallback."""
    return models_with_fallback(config.synth_model())


def build_synthesis_input(task: str, tool_call_log: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Pack tool call results into a single, size-budgeted user message for the synthesis step."""
    budget = _synth_input_budget()
    blocks: list[str] = []
    used = 0

    for entry in tool_call_log:
        name = entry.get("tool") or "tool"
        try:
            args = json.dumps(entry.get("inputs") or {}, ensure_ascii=False)
        except TypeError:
            args = "{}"
        if len(args) > 400:
            args = args[:400] + "..."
        body = serialize_result(entry.get("result"))
        chunk = f"### {name}\nInput: {args}\n{body}\n"
        if used + len(chunk) > budget:
            remain = budget - used
            if remain > 200:
                blocks.append(chunk[:remain] + "\n...[truncated]\n")
            break
        blocks.append(chunk)
        used += len(chunk)

    if not blocks:
        content = task.strip()
    else:
        content = (
            f"Câu hỏi người dùng:\n{task.strip()}\n\n"
            f"Dữ liệu từ {len(tool_call_log)} lần gọi tool "
            f"(hiển thị {len(blocks)}, đã rút gọn):\n\n" + "\n".join(blocks)
        )

    return [{"role": "user", "content": content}]


def synthesis_instructions(agent_system: str) -> str:
    """Build the system instructions for the synthesis round.

    Args:
        agent_system: (str) The agent's system prompt used during the tool-calling round.

    Returns:
        (str) The custom AGENT_SYNTH_SYSTEM prompt if configured; otherwise
        `agent_system` extended with a note that tool data has been gathered
        and no more tool calls should be made; empty/custom text as-is if
        `agent_system` is blank."""
    custom = (_prompts.AGENT_SYNTH_SYSTEM or "").strip()
    if custom:
        return custom
    base = (agent_system or "").strip()
    if not base:
        return custom
    return (
        f"{base}\n\n---\n"
        "Bạn đã thu đủ dữ liệu từ tool. KHÔNG gọi thêm tool.\n"
        "Viết câu trả lời hoàn chỉnh: tư vấn rõ ràng, ưu/nhược từ review, "
        "trả lời trực tiếp câu hỏi (đặc biệt có nên mua không)."
    )


def _should_fallback_synth(exc: Exception, model: str) -> bool:
    """(Internal) Decide whether a synthesis failure should trigger a fallback to the tool model.

    Args:
        exc: (Exception) The exception raised by the synthesis call.
        model: (str) The model that was being used when `exc` was raised.

    Returns:
        (bool) True if `model` differs from the tool model and `exc` looks like
        an upstream gateway error; False otherwise (already on the tool model,
        or not an upstream error)."""
    if model == config.tool_model():
        return False
    return is_upstream_gateway_error(exc)


def _is_stream_open_failure(exc: Exception) -> bool:
    """Check whether an exception indicates the upstream returned an empty/non-SSE body (reported by the OpenAI SDK as JSONDecodeError)."""
    if isinstance(exc, json.JSONDecodeError):
        return True
    return "expecting value" in str(exc).lower()


async def run_synthesis(
    *,
    system: str,
    task: str,
    tool_call_log: list[dict[str, Any]],
) -> str:
    """Run the non-streaming synthesis round, trying models in order until one succeeds (async).

    Args:
        system: (str) Agent system prompt to derive synthesis instructions from.
        task: (str) The original user task/question.
        tool_call_log: (list[dict[str, Any]]) Log of tool calls to summarize into the synthesis input.

    Returns:
        (str) The synthesized final answer text.

    Raises:
        AiLayerLLMError: If all candidate models fail or the LLM call returns an error."""
    input_items = build_synthesis_input(task, tool_call_log)
    instructions = synthesis_instructions(system)
    last_exc: Exception | None = None

    for model in synth_models_to_try():
        logger.info(
            log_event(
                "agent",
                "synthesis started",
                input_chars=len(input_items[0]["content"]),
                tools=len(tool_call_log),
                model=model,
            )
        )
        try:
            response = await create_response(
                task=TASK_AGENT_SYNTH,
                model=model,
                max_output_tokens=config.synth_max_tokens(),
                instructions=instructions,
                input=input_items,
            )
        except Exception as exc:
            last_exc = exc
            if _should_fallback_synth(exc, model):
                logger.warning(
                    log_event(
                        "agent",
                        "synthesis model fallback",
                        from_model=model,
                        to_model=config.tool_model(),
                        reason="upstream_error",
                    )
                )
                continue
            log_error(logger, exc, where="synthesis")
            raise AiLayerLLMError(
                user_message(exc),
                message_en=user_message(exc, "en"),
                cause=exc,
            ) from exc

        err = status_error(response)
        if err:
            raise AiLayerLLMError(f"Lỗi LLM: {err}", message_en=f"LLM error: {err}")
        return extract_response_text(response)

    log_error(logger, last_exc or AiLayerLLMError("synthesis failed"), where="synthesis")
    fail = last_exc or AiLayerLLMError("synthesis failed")
    raise AiLayerLLMError(
        user_message(fail),
        message_en=user_message(fail, "en"),
        cause=last_exc,
    ) from last_exc


async def iter_synthesis_deltas(
    *,
    system: str,
    task: str,
    tool_call_log: list[dict[str, Any]],
) -> AsyncGenerator[str]:
    """Stream the synthesis round text deltas, falling back across models and to non-streaming mode on failure (async).

    Args:
        system: (str) Agent system prompt to derive synthesis instructions from.
        task: (str) The original user task/question.
        tool_call_log: (list[dict[str, Any]]) Log of tool calls to summarize into the synthesis input.

    Returns:
        (AsyncGenerator[str]) Yields text deltas as they stream in; if streaming
        fails for every model, falls back to `run_synthesis` and yields the
        full text once.

    Raises:
        AiLayerLLMError: If both streaming and the non-streaming fallback fail."""
    input_items = build_synthesis_input(task, tool_call_log)
    instructions = synthesis_instructions(system)
    models = synth_models_to_try()
    last_exc: Exception | None = None

    for idx, model in enumerate(models):
        logger.info(
            log_event(
                "agent",
                "synthesis stream started",
                input_chars=len(input_items[0]["content"]),
                tools=len(tool_call_log),
                model=model,
            )
        )
        try:
            async with response_stream(
                task=TASK_AGENT_SYNTH,
                model=model,
                max_output_tokens=config.synth_max_tokens(),
                instructions=instructions,
                input=input_items,
            ) as stream:
                async for event in stream:
                    if event.type == "response.output_text.delta" and event.delta:
                        yield event.delta
            return
        except Exception as exc:
            last_exc = exc
            can_try_next = idx < len(models) - 1 and (
                _should_fallback_synth(exc, model) or _is_stream_open_failure(exc)
            )
            if can_try_next:
                logger.warning(
                    log_event(
                        "agent",
                        "synthesis stream model fallback",
                        from_model=model,
                        to_model=models[idx + 1],
                        error=exc,
                    )
                )
                continue
            log_error(logger, exc, where="synthesis_stream")
            break

    # Some gateways (e.g. xah + claude-opus) return an empty body when
    # stream:true, but non-stream still works — fall back to keep the stream
    # endpoint's UX alive.
    logger.warning(
        log_event(
            "agent",
            "synthesis stream unavailable",
            error=last_exc,
            fallback="non_stream",
        )
    )
    try:
        text = await run_synthesis(
            system=system,
            task=task,
            tool_call_log=tool_call_log,
        )
    except Exception as exc:
        if last_exc is not None:
            raise AiLayerLLMError(
                user_message(last_exc),
                message_en=user_message(last_exc, "en"),
                cause=last_exc,
            ) from exc
        log_error(logger, exc, where="synthesis_stream")
        raise AiLayerLLMError(
            user_message(exc),
            message_en=user_message(exc, "en"),
            cause=exc,
        ) from exc

    if text:
        yield text
