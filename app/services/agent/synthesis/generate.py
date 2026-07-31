import json
from typing import Any
from collections.abc import AsyncGenerator

import app.config.settings as settings
import app.services.prompts as _prompts
from app.ai.router import TASK_AGENT_SYNTH
from app.config.logger import Logger
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
    """(Nội bộ) Synth input budget `_synth_input_budget`.

    Returns:
        (int) Kết quả trả về."""
    base = getattr(settings, "AGENT_MAX_RESULT_CHARS", 8000) or 8000
    return min(max(base * 3, 12_000), _DEFAULT_SYNTH_INPUT_CHARS)


def models_with_fallback(primary: str, fallback: str | None = None) -> list[str]:
    """Danh sách model thử: primary rồi fallback (thường là tool_model)."""
    fb = fallback or config.tool_model()
    if primary != fb:
        return [primary, fb]
    return [primary]


def synth_models_to_try() -> list[str]:
    """Synth models to try.

    Returns:
        (list[str]) Kết quả trả về."""
    return models_with_fallback(config.synth_model())


def build_synthesis_input(task: str, tool_call_log: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Gom kết quả tool thành một user message gọn cho bước synthesis."""
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
    """Synthesis instructions.

    Args:
        agent_system: (str) Tham số `agent_system`.

    Returns:
        (str) Kết quả trả về."""
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
    """(Nội bộ) Should fallback synth `_should_fallback_synth`.

    Args:
        exc: (Exception) Tham số `exc`.
        model: (str) Tham số `model`.

    Returns:
        (bool) Kết quả trả về."""
    if model == config.tool_model():
        return False
    return is_upstream_gateway_error(exc)


def _is_stream_open_failure(exc: Exception) -> bool:
    """Upstream trả body rỗng / không phải SSE — OpenAI SDK báo JSONDecodeError."""
    if isinstance(exc, json.JSONDecodeError):
        return True
    return "expecting value" in str(exc).lower()


async def run_synthesis(
    *,
    system: str,
    task: str,
    tool_call_log: list[dict[str, Any]],
) -> str:
    """Chạy synthesis (async).

    Args:
        system: (str) Tham số `system`.
        task: (str) Tham số `task`.
        tool_call_log: (list[dict[str, Any]]) Tham số `tool_call_log`.

    Returns:
        (str) Kết quả trả về."""
    input_items = build_synthesis_input(task, tool_call_log)
    instructions = synthesis_instructions(system)
    last_exc: Exception | None = None

    for model in synth_models_to_try():
        logger.info(
            "[agent] synthesis input_chars=%d tools=%d model=%s",
            len(input_items[0]["content"]),
            len(tool_call_log),
            model,
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
                    "[agent] synthesis fallback after upstream error model=%s -> %s",
                    model,
                    config.tool_model(),
                )
                continue
            log_error(logger, exc, where="synthesis")
            vi, en = user_message(exc)
            raise AiLayerLLMError(vi, message_en=en, cause=exc) from exc

        err = status_error(response)
        if err:
            raise AiLayerLLMError(f"Lỗi LLM: {err}", message_en=f"LLM error: {err}")
        return extract_response_text(response)

    log_error(logger, last_exc or AiLayerLLMError("synthesis failed"), where="synthesis")
    vi, en = user_message(last_exc or AiLayerLLMError("synthesis failed"))
    raise AiLayerLLMError(vi, message_en=en, cause=last_exc) from last_exc


async def iter_synthesis_deltas(
    *,
    system: str,
    task: str,
    tool_call_log: list[dict[str, Any]],
) -> AsyncGenerator[str]:
    """Iter synthesis deltas (async).

    Args:
        system: (str) Tham số `system`.
        task: (str) Tham số `task`.
        tool_call_log: (list[dict[str, Any]]) Tham số `tool_call_log`.

    Returns:
        (AsyncGenerator[str]) Kết quả trả về."""
    input_items = build_synthesis_input(task, tool_call_log)
    instructions = synthesis_instructions(system)
    models = synth_models_to_try()
    last_exc: Exception | None = None

    for idx, model in enumerate(models):
        logger.info(
            "[agent] synthesis_stream input_chars=%d tools=%d model=%s",
            len(input_items[0]["content"]),
            len(tool_call_log),
            model,
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
                    "[agent] synthesis_stream fallback model=%s -> %s (%s)",
                    model,
                    models[idx + 1],
                    exc,
                )
                continue
            log_error(logger, exc, where="synthesis_stream")
            break

    # Một số gateway (vd. xah + claude-opus) trả body rỗng khi stream:true
    # nhưng non-stream vẫn OK — fallback giữ UX stream endpoint sống.
    logger.warning(
        "[agent] synthesis_stream unavailable (%s), falling back to non-stream synthesis",
        last_exc,
    )
    try:
        text = await run_synthesis(
            system=system,
            task=task,
            tool_call_log=tool_call_log,
        )
    except Exception as exc:
        if last_exc is not None:
            vi, en = user_message(last_exc)
            raise AiLayerLLMError(vi, message_en=en, cause=last_exc) from exc
        log_error(logger, exc, where="synthesis_stream")
        vi, en = user_message(exc)
        raise AiLayerLLMError(vi, message_en=en, cause=exc) from exc

    if text:
        yield text
