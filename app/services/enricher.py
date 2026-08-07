from app.services.enricher_collect import (
    collect_tool_results,
    detect_source_label,
    movie_name_from_task,
)
from app.services.review_summarizer import summarize_reviews


async def enrich_agent_result(
    result_text: str,
    tool_calls: list[dict],
    iterations: int,
    task: str = "",
    *,
    include_summary: bool = True,
) -> dict:
    """Build the UI-facing result payload after an agent run finishes.

    Extracts reviews, videos, and sources from the tool call log, infers
    the movie name, and (optionally) generates an LLM review summary.

    Args:
        result_text: The agent's final text response.
        tool_calls: Log of tool calls made during the run; each entry has
            "tool", "inputs", and "result" keys.
        iterations: Number of agent loop iterations executed.
        task: Original task/question text, used to infer the movie name.
        include_summary: Whether to generate a review summary when reviews
            were collected.

    Returns:
        A dict with "result", "data" (review_summary, sources, videos,
        reviews_analyzed, review_source), "tool_calls", and "iterations".
    """
    all_reviews, all_videos, sources = collect_tool_results(tool_calls)
    source_label = detect_source_label(tool_calls)
    movie_name = movie_name_from_task(task, all_videos)
    review_summary = None
    if include_summary and all_reviews:
        review_summary = await summarize_reviews(
            all_reviews,
            movie=movie_name,
            source=source_label,
            task=task,
        )
    return {
        "result": result_text,
        "data": {
            "review_summary": review_summary,
            "sources": sources,
            "videos": all_videos,
            "reviews_analyzed": len(all_reviews),
            "review_source": source_label,
        },
        "tool_calls": [{"tool": c["tool"], "inputs": c["inputs"]} for c in tool_calls],
        "iterations": iterations,
    }
