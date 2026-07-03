import json
from app.clients import data_miner
from app.config.logger import Logger
from app.exceptions import AiLayerUpstreamError
from app.utils.llm_responses import complete_json

logger = Logger.get(__name__)
_SYSTEM = "You are an AI assistant analyzing YouTube content.\nBe concise. Always respond in the same language as the video content when possible."


def _parse_json(raw: str, context: str) -> dict:
    """(Nội bộ) Phân tích json.

    Args:
        raw: (str) Tham số `raw`.
        context: (str) Tham số `context`.

    Returns:
        (Dict) Kết quả trả về."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error("[youtube] json parse failed context=%s error=%s raw=%s", context, e, raw[:200])
        raise AiLayerUpstreamError(f"ChatGPT returned invalid JSON in {context}: {e}", cause=e) from e


async def summarize_video(video_id: str) -> dict:
    """Tóm tắt video (async).

    Args:
        video_id: (str) Tham số `video_id`.

    Returns:
        (Dict) Kết quả trả về."""
    detail = await data_miner.get_video_detail(video_id)
    prompt = f"""Summarize this YouTube video:\nTitle: {detail.get("title")}\nChannel: {detail.get("author")}\nDescription: {(detail.get("description") or "")[:1000]}\nDuration: {detail.get("length_seconds")}s\nViews: {detail.get("views")}\n\nReturn JSON: {{"summary": "...", "key_points": ["..."], "tags": ["..."], "sentiment": "positive|neutral|negative"}}"""
    raw = await complete_json(prompt, _SYSTEM)
    result = _parse_json(raw, "summarize_video")
    result["video_id"] = video_id
    result["title"] = detail.get("title")
    return result


async def analyze_comments(video_id: str) -> dict:
    """Analyze comments (async).

    Args:
        video_id: (str) Tham số `video_id`.

    Returns:
        (Dict) Kết quả trả về."""
    data = await data_miner.get_video_comments(video_id, max_comments=100)
    comments = data.get("comments", [])
    if not comments:
        return {"video_id": video_id, "total": 0, "insights": None}
    sample = "\n".join(f"- {c.get('content', '')[:200]}" for c in comments[:50])
    prompt = f'Analyze these YouTube comments for video_id={video_id}:\n{sample}\n\nReturn JSON: {{\n  "overall_sentiment": "positive|neutral|negative|mixed",\n  "top_topics": ["..."],\n  "common_questions": ["..."],\n  "audience_insight": "..."\n}}'
    raw = await complete_json(prompt, _SYSTEM)
    result = _parse_json(raw, "analyze_comments")
    result["video_id"] = video_id
    result["total_analyzed"] = len(comments)
    return result


async def analyze_trends(limit: int = 20) -> dict:
    """Analyze trends (async).

    Args:
        limit: (int, mặc định 20) Tham số `limit`.

    Returns:
        (Dict) Kết quả trả về."""
    data = await data_miner.get_trending(max_results=limit)
    videos: list[dict] = data.get("videos", data) if isinstance(data, dict) else data
    titles = "\n".join(
        (f"{i + 1}. [{v.get('channel', '')}] {v.get('title', '')}" for i, v in enumerate(videos[:limit]))
    )
    prompt = f'Analyze these trending YouTube videos and identify patterns:\n{titles}\n\nReturn JSON: {{\n  "dominant_themes": ["..."],\n  "trending_formats": ["..."],\n  "top_channels": ["..."],\n  "insights": "..."\n}}'
    raw = await complete_json(prompt, _SYSTEM)
    result = _parse_json(raw, "analyze_trends")
    result["analyzed_count"] = len(videos)
    return result
