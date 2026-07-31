from collections.abc import AsyncGenerator

from app.services.agent.iterate import run_agent_events


async def run_agent_stream(
    task: str, tools: list[dict], max_iter: int = 10, system: str | None = None
) -> AsyncGenerator[str, None]:
    """Chạy agent stream (async) — map events → SSE."""
    async for event in run_agent_events(task, tools, max_iter, system, stream_llm=True):
        yield event.to_sse()
