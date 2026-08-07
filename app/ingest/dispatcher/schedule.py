from typing import Any
from app.config.logger import Logger, log_event
from app.ingest.dispatcher.routes import route_tool
from app.ingest.mappers.unwrap import unwrap_result
from app.rag.movie_hint import extract_movie_name

logger = Logger.get(__name__)


def _movie_hint(task: str) -> str:
    """Derive a short movie/product hint from a task description, truncated to 120 chars.

    Args:
        task: Free-text task description to extract a movie/product name from.

    Returns:
        The extracted name (max 120 chars), or "" if nothing could be extracted.
    """
    name = extract_movie_name(task)
    return name[:120] if name else ""


async def schedule_tool_ingest(tool_name: str, inputs: dict, result: Any, *, task: str = "") -> None:
    """Unwrap a tool's result and route it into the ingest pipeline, swallowing errors.

    Called after an agent tool finishes so that any video/comment/transcript data
    it returned gets ingested in the background without affecting the agent's response.

    Args:
        tool_name: Name of the agent tool that was called (e.g. "youtube_search").
        inputs: Original arguments the tool was called with.
        result: Raw return value of the tool call, in the standard success/data/error envelope.
        task: Original task description, used to derive a movie/product hint.

    Returns:
        None. Any exception raised while routing is caught and logged as a warning.
    """
    data = unwrap_result(result)
    if data is None:
        return
    platform = "tiktok" if tool_name.startswith("tiktok_") else "youtube"
    try:
        await route_tool(tool_name, inputs, data, movie_hint=_movie_hint(task), platform=platform)
    except Exception as exc:
        logger.warning(log_event("ingest", "schedule failed", tool=tool_name, error=exc))
