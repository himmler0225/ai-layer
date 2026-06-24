from __future__ import annotations

from typing import AsyncGenerator, Dict, List

from app.services.agent import config
from app.utils.openai_client import get_openai_client
from app.utils.openai_responses import create_response, extract_response_text, status_error


async def run_synthesis(*, system: str, input_items: List[Dict]) -> str:
    """Gọi model tổng hợp (non-stream)."""
    response = await create_response(
        model=config.synth_model(),
        max_output_tokens=config.synth_max_tokens(),
        instructions=system,
        input=input_items,
    )
    err = status_error(response)
    if err:
        raise RuntimeError(err)
    return extract_response_text(response)


async def iter_synthesis_deltas(
    *,
    system: str,
    input_items: List[Dict],
) -> AsyncGenerator[str, None]:
    """Stream từng đoạn text từ model tổng hợp."""
    async with get_openai_client().responses.stream(
        model=config.synth_model(),
        max_output_tokens=config.synth_max_tokens(),
        instructions=system,
        input=input_items,
    ) as stream:
        async for event in stream:
            if event.type == "response.output_text.delta":
                yield event.delta