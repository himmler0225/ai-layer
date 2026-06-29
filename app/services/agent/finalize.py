from __future__ import annotations
from typing import Any, Dict, List
from app.services.enricher import enrich_agent_result

async def finish(*, session_id: str, task: str, iteration: int, tool_call_log: List[Dict], final_text: str, include_summary: bool=True) -> Dict[str, Any]:
    """Hoàn tất `finish` (async).

    Args:
        session_id: (str) Tham số `session_id`.
        task: (str) Tham số `task`.
        iteration: (int) Tham số `iteration`.
        tool_call_log: (List[Dict]) Tham số `tool_call_log`.
        final_text: (str) Tham số `final_text`.
        include_summary: (bool, mặc định True) Tham số `include_summary`.

    Returns:
        (Dict[str, Any]) Kết quả trả về."""
    return await enrich_agent_result(final_text, tool_call_log, iteration, task=task, include_summary=include_summary)
