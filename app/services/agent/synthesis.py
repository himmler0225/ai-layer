from __future__ import annotations

from typing import AsyncGenerator, Dict, List

import app.services.prompts as _prompts
from app.ai.router import TASK_AGENT_SYNTH
from app.config.logger import Logger
from app.services.agent import config
from app.utils.openai_errors import log_error, user_message
from app.utils.openai_responses import (create_response, extract_response_text,
                                        response_stream_with_retry,
                                        status_error)

logger = Logger.get(__name__)


def synthesis_instructions(agent_system: str) -> str:
    """Prompt riêng cho bước viết câu trả lời — không tái dùng prompt gọi tool."""
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


async def run_synthesis(*, system: str, input_items: List[Dict]) -> str:
    instructions = synthesis_instructions(system)
    try:
        response = await create_response(
            task=TASK_AGENT_SYNTH,
            model=config.synth_model(),
            max_output_tokens=config.synth_max_tokens(),
            instructions=instructions,
            input=input_items,
        )
    except Exception as exc:
        log_error(logger, exc, where="synthesis")
        raise RuntimeError(user_message(exc)) from exc
    err = status_error(response)
    if err:
        raise RuntimeError(err)
    return extract_response_text(response)


async def iter_synthesis_deltas(
    *,
    system: str,
    input_items: List[Dict],
) -> AsyncGenerator[str, None]:
    instructions = synthesis_instructions(system)
    try:
        async with response_stream_with_retry(
            task=TASK_AGENT_SYNTH,
            model=config.synth_model(),
            max_output_tokens=config.synth_max_tokens(),
            instructions=instructions,
            input=input_items,
        ) as stream:
            async for event in stream:
                if event.type == "response.output_text.delta" and event.delta:
                    yield event.delta
    except Exception as exc:
        log_error(logger, exc, where="synthesis_stream")
        raise RuntimeError(user_message(exc)) from exc
