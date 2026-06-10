import re
from typing import Dict
from urllib.parse import urlparse, parse_qs


def extract_id_from_url(url: str, platform: str = None) -> Dict:
    url = url.strip()
    detected = platform or _detect_platform(url)
    if detected == "youtube":
        return _youtube(url)
    if detected == "tiktok":
        return _tiktok(url)
    return {"error": f"Unsupported URL: {url}"}


def _detect_platform(url: str) -> str:
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    if "tiktok.com" in url:
        return "tiktok"
    return "unknown"


def _youtube(url: str) -> Dict:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "v" in qs:
        return {"platform": "youtube", "video_id": qs["v"][0]}
    if "youtu.be" in url:
        vid = parsed.path.strip("/").split("?")[0]
        if vid:
            return {"platform": "youtube", "video_id": vid}
    m = re.search(r"/shorts/([A-Za-z0-9_-]{11})", url)
    if m:
        return {"platform": "youtube", "video_id": m.group(1)}
    return {"error": "Could not extract YouTube video_id"}


def _tiktok(url: str) -> Dict:
    # tiktok.com/@username/video/VIDEO_ID
    m = re.search(r"tiktok\.com/@[^/]+/video/(\d+)", url)
    if m:
        return {"platform": "tiktok", "url": url}
    # vt.tiktok.com / vm.tiktok.com — short links, can't resolve without HTTP
    if re.search(r"(vt|vm)\.tiktok\.com", url):
        return {"platform": "tiktok", "url": url, "note": "short link — use url directly for tiktok_comments/tiktok_video_info"}
    return {"error": "Could not extract TikTok video_id from URL"}
