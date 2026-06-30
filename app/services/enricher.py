from __future__ import annotations

from typing import Dict, List

from app.services.enricher_collect import (
    collect_tool_results,
    detect_source_label,
    movie_name_from_task,
)
from app.services.review_summarizer import summarize_reviews


async def enrich_agent_result(
    result_text: str,
    tool_calls: List[Dict],
    iterations: int,
    task: str = "",
    *,
    include_summary: bool = True,
) -> Dict:
    """Bổ sung metadata UI sau khi agent hoàn tất."""
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
