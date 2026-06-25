from __future__ import annotations

from typing import Any, Dict, List

from app.services.enricher import enrich_agent_result


async def finish(
    *,
    session_id: str,
    task: str,
    iteration: int,
    tool_call_log: List[Dict],
    final_text: str,
    include_summary: bool = True,
) -> Dict[str, Any]:
    return await enrich_agent_result(
        final_text, tool_call_log, iteration, task=task, include_summary=include_summary,
    )
