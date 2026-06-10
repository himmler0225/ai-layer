from typing import Dict, List
from urllib.parse import quote
from .review_summarizer import summarize_reviews

def _youtube_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"

def _youtube_search_url(query: str) -> str:
    return f"https://www.youtube.com/results?search_query={quote(query)}"

def _collect_all(tool_calls: List[Dict]):
    seen_urls:   set       = set()
    all_reviews: List[Dict] = []
    all_videos:  List[Dict] = []
    sources:     List[Dict] = []

    def _add_source(label: str, url: str, kind: str):
        if url not in seen_urls:
            seen_urls.add(url)
            sources.append({"label": label[:80], "url": url, "type": kind})

    for call in tool_calls:
        tool   = call.get("tool", "")
        inputs = call.get("inputs", {})
        result = call.get("result", {})

        if not isinstance(result, dict):
            continue

        if tool == "youtube_search":
            q = inputs.get("keyword") or inputs.get("query", "")
            _add_source(f'YouTube: "{q}"', _youtube_search_url(q), "search")
            for v in (result.get("results") or result.get("videos") or []):
                vid = v.get("video_id")
                if vid:
                    url = _youtube_url(vid)
                    _add_source(v.get("title", vid)[:80], url, "video")
                    all_videos.append({
                        "video_id":  vid,
                        "title":     v.get("title"),
                        "channel":   v.get("channel"),
                        "views":     v.get("view_count"),
                        "source_url": url,
                    })

        elif tool == "youtube_get_detail":
            vid = result.get("video_id") or inputs.get("video_id")
            if vid:
                url = _youtube_url(vid)
                _add_source(result.get("title", vid)[:80], url, "video")
                all_videos.append({
                    "video_id":   vid,
                    "title":      result.get("title"),
                    "channel":    result.get("author"),
                    "views":      result.get("views"),
                    "duration":   result.get("length_seconds"),
                    "description": (result.get("description") or "")[:300],
                    "source_url": url,
                })

        elif tool == "youtube_get_comments":
            vid = inputs.get("video_id")
            url = _youtube_url(vid) if vid else None
            for c in (result.get("comments") or []):
                all_reviews.append({
                    "content":    c.get("content") or c.get("text") or "",
                    "source_url": url,
                })
            if url:
                _add_source(f"YouTube comments: {vid}", url, "reviews")

    return all_reviews, all_videos, sources

async def enrich_agent_result(result_text: str, tool_calls: List[Dict], iterations: int) -> Dict:
    all_reviews, all_videos, sources = _collect_all(tool_calls)

    video_name = all_videos[0].get("title", "video") if all_videos else "video"
    review_summary = await summarize_reviews(all_reviews, video_name, "YouTube") if all_reviews else None

    return {
        "result": result_text,
        "data": {
            "review_summary":   review_summary,
            "sources":          sources,
            "videos":           all_videos,
            "reviews_analyzed": len(all_reviews),
        },
        "tool_calls": [{"tool": c["tool"], "inputs": c["inputs"]} for c in tool_calls],
        "iterations": iterations,
    }
