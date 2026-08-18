from pydantic import BaseModel, Field

from app.clients import data_miner
from app.config.logger import Logger, log_event
from app.exceptions import AiLayerUpstreamError
from app.utils.llm_responses import complete_structured

logger = Logger.get(__name__)
_SYSTEM = "You are an AI assistant analyzing YouTube content.\nBe concise. Always respond in the same language as the video content when possible."


class VideoSummaryResult(BaseModel):
    """LLM response shape for `summarize_video`."""

    summary: str
    key_points: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    sentiment: str = ""


class CommentAnalysisResult(BaseModel):
    """LLM response shape for `analyze_comments`."""

    overall_sentiment: str = ""
    top_topics: list[str] = Field(default_factory=list)
    common_questions: list[str] = Field(default_factory=list)
    audience_insight: str = ""


class TrendAnalysisResult(BaseModel):
    """LLM response shape for `analyze_trends`."""

    dominant_themes: list[str] = Field(default_factory=list)
    trending_formats: list[str] = Field(default_factory=list)
    top_channels: list[str] = Field(default_factory=list)
    insights: str = ""


async def summarize_video(video_id: str) -> dict:
    """Fetch a video's details and ask the LLM to summarize it.

    Args:
        video_id: YouTube video ID to summarize.

    Returns:
        A dict with "summary", "key_points", "tags", "sentiment" (from the
        LLM), plus "video_id" and "title".
    """
    detail = (await data_miner.get_video_detail(video_id)).get("detail", {})
    prompt = f"""Summarize this YouTube video:\nTitle: {detail.get("title")}\nChannel: {detail.get("author")}\nDescription: {(detail.get("description") or "")[:1000]}\nDuration: {detail.get("length_seconds")}s\nViews: {detail.get("views")}"""
    try:
        parsed = await complete_structured(prompt, _SYSTEM, VideoSummaryResult)
    except Exception as e:
        logger.error(log_event("youtube", "llm structured output failed", context="summarize_video", error=e))
        raise AiLayerUpstreamError(f"ChatGPT returned invalid output in summarize_video: {e}", cause=e) from e
    result = parsed.model_dump()
    result["video_id"] = video_id
    result["title"] = detail.get("title")
    return result


async def analyze_comments(video_id: str) -> dict:
    """Fetch up to 100 comments for a video and ask the LLM to analyze audience sentiment.

    Args:
        video_id: YouTube video ID whose comments should be analyzed.

    Returns:
        If there are no comments, {"video_id", "total": 0, "insights": None}.
        Otherwise a dict with "overall_sentiment", "top_topics",
        "common_questions", "audience_insight" (from the LLM), plus
        "video_id" and "total_analyzed".
    """
    data = await data_miner.get_video_comments(video_id, max_comments=100)
    comments = data.get("comments", [])
    if not comments:
        return {"video_id": video_id, "total": 0, "insights": None}
    sample = "\n".join(f"- {c.get('content', '')[:200]}" for c in comments[:50])
    prompt = f"Analyze these YouTube comments for video_id={video_id}:\n{sample}"
    try:
        parsed = await complete_structured(prompt, _SYSTEM, CommentAnalysisResult)
    except Exception as e:
        logger.error(log_event("youtube", "llm structured output failed", context="analyze_comments", error=e))
        raise AiLayerUpstreamError(f"ChatGPT returned invalid output in analyze_comments: {e}", cause=e) from e
    result = parsed.model_dump()
    result["video_id"] = video_id
    result["total_analyzed"] = len(comments)
    return result


async def analyze_trends(limit: int = 20) -> dict:
    """Fetch trending YouTube videos and ask the LLM to identify patterns across them.

    Args:
        limit: Maximum number of trending videos to fetch and analyze.

    Returns:
        A dict with "dominant_themes", "trending_formats", "top_channels",
        "insights" (from the LLM), plus "analyzed_count".
    """
    data = await data_miner.get_trending(max_results=limit)
    videos: list[dict] = data.get("results", []) if isinstance(data, dict) else data
    titles = "\n".join(
        (f"{i + 1}. [{v.get('channel', '')}] {v.get('title', '')}" for i, v in enumerate(videos[:limit]))
    )
    prompt = f"Analyze these trending YouTube videos and identify patterns:\n{titles}"
    try:
        parsed = await complete_structured(prompt, _SYSTEM, TrendAnalysisResult)
    except Exception as e:
        logger.error(log_event("youtube", "llm structured output failed", context="analyze_trends", error=e))
        raise AiLayerUpstreamError(f"ChatGPT returned invalid output in analyze_trends: {e}", cause=e) from e
    result = parsed.model_dump()
    result["analyzed_count"] = len(videos)
    return result
