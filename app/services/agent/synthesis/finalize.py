from typing import Any
from app.services.enricher import enrich_agent_result


async def finish(
    *,
    session_id: str,
    task: str,
    iteration: int,
    tool_call_log: list[dict],
    final_text: str,
    include_summary: bool = True,
) -> dict[str, Any]:
    """Enrich the agent's final answer into the full response payload (async).

    Args:
        session_id: (str) Agent run session id (currently unused, kept for interface consistency).
        task: (str) The original user task/question.
        iteration: (int) Final iteration count reached.
        tool_call_log: (List[Dict]) Log of all tool calls made during the run.
        final_text: (str) The agent's synthesized final answer text.
        include_summary: (bool, default True) Whether to include a review summary in the enriched result.

    Returns:
        (Dict[str, Any]) Enriched result payload produced by `enrich_agent_result`."""
    return await enrich_agent_result(final_text, tool_call_log, iteration, task=task, include_summary=include_summary)
