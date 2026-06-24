from __future__ import annotations

from typing import Any, Dict, List

from app.db.mongo import log_agent_run
from app.services.enricher import enrich_agent_result


async def finish(
    *,
    session_id: str,
    task: str,
    iteration: int,
    tool_call_log: List[Dict],
    final_text: str,
) -> Dict[str, Any]:
    """Gom dữ liệu hiển thị UI và ghi log vào Mongo."""
    enriched = await enrich_agent_result(final_text, tool_call_log, iteration, task=task)
    await log_agent_run(
        session_id,
        task,
        iteration,
        tool_call_log,
        final_text,
        enriched["data"].get("sources", []),
        enriched["data"].get("videos", []),
        enriched["data"].get("reviews_analyzed", 0),
    )
    return enriched