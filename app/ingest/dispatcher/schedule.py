from __future__ import annotations
from typing import Any
from app.config.logger import Logger
from app.ingest.dispatcher.routes import route_tool
from app.ingest.mappers.unwrap import unwrap_result
from app.rag.movie_hint import extract_movie_name
logger = Logger.get(__name__)

def _movie_hint(task: str) -> str:
    """(Nội bộ) Product hint.

    Args:
        task: (str) Tham số `task`.

    Returns:
        (str) Kết quả trả về."""
    name = extract_movie_name(task)
    return name[:120] if name else ''

async def schedule_tool_ingest(tool_name: str, inputs: dict, result: Any, *, task: str='') -> None:
    """Lên lịch tool ingest (async).

    Args:
        tool_name: (str) Tham số `tool_name`.
        inputs: (dict) Tham số `inputs`.
        result: (Any) Tham số `result`.
        task: (str, mặc định '') Tham số `task`.

    Returns:
        (None) Kết quả trả về."""
    data = unwrap_result(result)
    if data is None:
        return
    platform = 'tiktok' if tool_name.startswith('tiktok_') else 'youtube'
    try:
        await route_tool(tool_name, inputs, data, movie_hint=_movie_hint(task), platform=platform)
    except Exception as exc:
        logger.warning('[ingest] schedule failed tool=%s: %s', tool_name, exc)
