import json
from app.config.logger import Logger
from typing import Dict, List
from app.clients import data_miner
from app.services.claude import complete_json

logger = Logger.get(__name__)

_SYSTEM = """You are an AI assistant analyzing YouTube content.
Be concise. Always respond in the same language as the video content when possible."""

def _parse_json(raw: str, context: str) -> Dict:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error("JSON parse error in %s: %s | raw=%s", context, e, raw[:200])
        raise ValueError(f"Claude returned invalid JSON in {context}: {e}") from e

async def summarize_video(video_id: str) -> Dict:
    detail = await data_miner.get_video_detail(video_id)

    prompt = f"""Summarize this YouTube video:
Title: {detail.get('title')}
Channel: {detail.get('author')}
Description: {(detail.get('description') or '')[:1000]}
Duration: {detail.get('length_seconds')}s
Views: {detail.get('views')}

Return JSON: {{"summary": "...", "key_points": ["..."], "tags": ["..."], "sentiment": "positive|neutral|negative"}}"""

    raw = await complete_json(prompt, _SYSTEM)
    result = _parse_json(raw, "summarize_video")
    result["video_id"] = video_id
    result["title"] = detail.get("title")
    return result

async def analyze_comments(video_id: str) -> Dict:
    data = await data_miner.get_video_comments(video_id, max_comments=100)
    comments = data.get("comments", [])
    if not comments:
        return {"video_id": video_id, "total": 0, "insights": None}

    sample = "\n".join(
        f"- {c.get('content', '')[:200]}"
        for c in comments[:50]
    )

    prompt = f"""Analyze these YouTube comments for video_id={video_id}:
{sample}

Return JSON: {{
  "overall_sentiment": "positive|neutral|negative|mixed",
  "top_topics": ["..."],
  "common_questions": ["..."],
  "audience_insight": "..."
}}"""

    raw = await complete_json(prompt, _SYSTEM)
    result = _parse_json(raw, "analyze_comments")
    result["video_id"] = video_id
    result["total_analyzed"] = len(comments)
    return result

async def analyze_trends(limit: int = 20) -> Dict:
    data = await data_miner.get_trending(max_results=limit)
    videos: List[Dict] = data.get("videos", data) if isinstance(data, dict) else data

    titles = "\n".join(
        f"{i+1}. [{v.get('channel', '')}] {v.get('title', '')}"
        for i, v in enumerate(videos[:limit])
    )

    prompt = f"""Analyze these trending YouTube videos and identify patterns:
{titles}

Return JSON: {{
  "dominant_themes": ["..."],
  "trending_formats": ["..."],
  "top_channels": ["..."],
  "insights": "..."
}}"""

    raw = await complete_json(prompt, _SYSTEM)
    result = _parse_json(raw, "analyze_trends")
    result["analyzed_count"] = len(videos)
    return result
