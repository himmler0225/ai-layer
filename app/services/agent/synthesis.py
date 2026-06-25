from __future__ import annotations

from typing import AsyncGenerator, Dict, List

from app.config.logger import Logger
from app.services.agent import config
from app.utils.openai_errors import log_error, user_message
from app.utils.openai_responses import (
    create_response,
    extract_response_text,
    response_stream_with_retry,
    status_error,
)

logger = Logger.get(__name__)


async def run_synthesis(*, system: str, input_items: List[Dict]) -> str:
    try:
        response = await create_response(
            model=config.synth_model(),
            max_output_tokens=config.synth_max_tokens(),
            instructions=system,
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
    try:
        async with response_stream_with_retry(
            model=config.synth_model(),
            max_output_tokens=config.synth_max_tokens(),
            instructions=system,
            input=input_items,
        ) as stream:
            async for event in stream:
                if event.type == "response.output_text.delta" and event.delta:
                    yield event.delta
    except Exception as exc:
        log_error(logger, exc, where="synthesis_stream")
        raise RuntimeError(user_message(exc)) from exc
