from typing import Dict, List, Optional
from urllib.parse import quote
from .review_summarizer import summarize_reviews

def _youtube_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"

def _youtube_search_url(query: str) -> str:
    return f"https://www.youtube.com/results?search_query={quote(query)}"

def _tiktok_url(aweme_id: str) -> str:
    return f"https://www.tiktok.com/@_/video/{aweme_id}"

def _best_thumb(thumbnails, video_id: str = "") -> Optional[str]:
    if isinstance(thumbnails, list):
        for t in reversed(thumbnails):
            if isinstance(t, dict):
                url = t.get("url", "")
                if url:
                    if url.startswith("//"):
                        url = "https:" + url
                    return url
    if video_id:
        return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    return None

def _safe(item) -> Optional[Dict]:
    return item if isinstance(item, dict) else None

def _fmt_views(views) -> Optional[str]:
    try:
        n = int(views)
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M views"
        if n >= 1_000:
            return f"{n // 1_000}K views"
        return f"{n} views"
    except (TypeError, ValueError):
        return str(views) if views else None

def _unwrap(result) -> dict:
    if isinstance(result, dict) and "success" in result and "data" in result:
        inner = result.get("data")
        if isinstance(inner, (dict, list)):
            return inner if isinstance(inner, dict) else {"_list": inner}
    return result if isinstance(result, dict) else {}

def _collect_all(tool_calls: List[Dict]):
    seen_urls:   set       = set()
    all_reviews: List[Dict] = []
    all_videos:  List[Dict] = []
    sources:     List[Dict] = []

    def _add_source(label: str, url: str, kind: str, **meta):
        if url not in seen_urls:
            seen_urls.add(url)
            source = {"label": label[:80], "url": url, "type": kind}
            source.update({k: v for k, v in meta.items() if v is not None})
            sources.append(source)

    for call in tool_calls:
        tool   = call.get("tool", "")
        inputs = call.get("inputs", {})
        result = _unwrap(call.get("result", {}))

        if not isinstance(result, dict):
            continue

        if tool == "youtube_search":
            q = inputs.get("keyword") or inputs.get("query", "")
            _add_source(f'YouTube: "{q}"', _youtube_search_url(q), "search", platform="youtube")
            video_list = (
                result.get("_list")              # unwrapped bare list
                or result.get("results")
                or result.get("videos")
                or []
            )
            for raw_v in video_list:
                v = _safe(raw_v)
                if not v:
                    continue
                vid = v.get("video_id")
                if vid:
                    url = _youtube_url(vid)
                    thumb = _best_thumb(v.get("thumbnails", []) or [], vid)
                    _add_source(
                        (v.get("title") or vid)[:80], url, "video",
                        thumbnail=thumb, channel=v.get("channel"),
                        views=_fmt_views(v.get("view_count")), platform="youtube",
                    )
                    all_videos.append({
                        "video_id": vid, "title": v.get("title"),
                        "channel": v.get("channel"), "views": v.get("view_count"),
                        "thumbnail": thumb, "source_url": url,
                    })

        elif tool == "youtube_get_detail":
            vid = result.get("video_id") or inputs.get("video_id")
            if vid:
                url = _youtube_url(vid)
                thumbs = result.get("thumbnails", []) or result.get("thumbnail", [])
                thumb = _best_thumb(thumbs, vid)
                channel = result.get("author") or result.get("channel")
                views = result.get("views") or result.get("view_count")
                _add_source(
                    (result.get("title") or vid)[:80], url, "video",
                    thumbnail=thumb, channel=channel,
                    views=_fmt_views(views), platform="youtube",
                )
                all_videos.append({
                    "video_id": vid, "title": result.get("title"),
                    "channel": channel, "views": views,
                    "duration": result.get("length_seconds"),
                    "description": (result.get("description") or "")[:300],
                    "thumbnail": thumb, "source_url": url,
                })

        elif tool in ("youtube_get_comments", "youtube_get_transcript"):
            vid = inputs.get("video_id")
            url = _youtube_url(vid) if vid else None
            for raw_c in (result.get("comments") or result.get("_list") or []):
                c = _safe(raw_c)
                if c:
                    all_reviews.append({"content": c.get("content") or c.get("text") or "", "source_url": url})
            if url:
                _add_source(f"YouTube: {vid}", url, "reviews", platform="youtube")

        elif tool in ("youtube_get_comments_batch", "youtube_get_transcript_batch"):
            for raw_vr in (result.get("results") or result.get("_list") or []):
                vid_result = _safe(raw_vr)
                if not vid_result:
                    continue
                vid = vid_result.get("video_id")
                url = _youtube_url(vid) if vid else None
                for raw_c in (vid_result.get("comments") or vid_result.get("segments") or []):
                    c = _safe(raw_c)
                    if c:
                        all_reviews.append({"content": c.get("content") or c.get("text") or "", "source_url": url})
                if url and (vid_result.get("comments") or vid_result.get("segments")):
                    _add_source(f"YouTube: {vid}", url, "reviews", platform="youtube")

        elif tool == "tiktok_search":
            q = inputs.get("keyword", "")
            for raw_v in (result.get("videos") or result.get("items") or result.get("_list") or []):
                v = _safe(raw_v)
                if not v:
                    continue
                aweme = v.get("aweme_id") or v.get("id", "")
                if not aweme:
                    continue
                url = _tiktok_url(aweme)
                title = v.get("desc") or v.get("title") or aweme
                author = (v.get("author") or {}).get("nickname") or v.get("author_name", "")
                plays = (v.get("statistics") or {}).get("play_count") or v.get("play_count")
                cover = v.get("video", {}).get("cover", {}).get("url_list", [])
                thumb = cover[0] if cover else None
                _add_source(
                    title[:80], url, "video",
                    thumbnail=thumb, channel=author,
                    views=_fmt_views(plays), platform="tiktok",
                )
                all_videos.append({"video_id": aweme, "title": title, "channel": author, "views": plays, "thumbnail": thumb, "source_url": url})

        elif tool in ("tiktok_comments", "tiktok_transcript"):
            url = inputs.get("url", "")
            for c in (result.get("comments") or result.get("segments") or []):
                all_reviews.append({"content": c.get("text") or c.get("content") or "", "source_url": url})
            if url:
                _add_source(f"TikTok: {url[:40]}", url, "reviews", platform="tiktok")

        elif tool == "tiktok_video_info":
            url = inputs.get("url", "")
            v = result
            aweme = v.get("aweme_id") or v.get("id", "")
            title = v.get("desc") or v.get("title") or aweme
            author = (v.get("author") or {}).get("nickname") or ""
            plays = (v.get("statistics") or {}).get("play_count")
            cover = v.get("video", {}).get("cover", {}).get("url_list", [])
            thumb = cover[0] if cover else None
            if url:
                _add_source(title[:80], url, "video", thumbnail=thumb, channel=author, views=_fmt_views(plays), platform="tiktok")

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
