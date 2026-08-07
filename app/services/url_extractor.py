import re
from urllib.parse import parse_qs, urlparse


def extract_id_from_url(url: str, platform: str = None) -> dict:
    """Extract the platform and video id/URL from a YouTube or TikTok link.

    Args:
        url: The video URL to parse.
        platform: Force parsing as this platform ("youtube" or "tiktok")
            instead of auto-detecting from the URL.

    Returns:
        A dict describing the video, e.g. {"platform": ..., "video_id":
        ...} for YouTube or {"platform": "tiktok", "url": ...} for TikTok,
        or {"error": ...} if the URL is unsupported or couldn't be parsed.
    """
    url = url.strip()
    detected = platform or _detect_platform(url)
    if detected == "youtube":
        return _youtube(url)
    if detected == "tiktok":
        return _tiktok(url)
    return {"error": f"Unsupported URL: {url}"}


def _detect_platform(url: str) -> str:
    """Detect the video platform from a URL's domain.

    Args:
        url: The URL to inspect.

    Returns:
        "youtube" if the domain is youtube.com/youtu.be, "tiktok" if it's
        tiktok.com, otherwise "unknown".
    """
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    if "tiktok.com" in url:
        return "tiktok"
    return "unknown"


def _youtube(url: str) -> dict:
    """Extract a video id from a YouTube URL.

    Handles standard "watch?v=", "youtu.be/" short links, and "/shorts/"
    URLs.

    Args:
        url: A YouTube URL.

    Returns:
        {"platform": "youtube", "video_id": ...} on success, or
        {"error": ...} if no video id could be found.
    """
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "v" in qs:
        return {"platform": "youtube", "video_id": qs["v"][0]}
    if "youtu.be" in url:
        vid = parsed.path.strip("/").split("?")[0]
        if vid:
            return {"platform": "youtube", "video_id": vid}
    m = re.search("/shorts/([A-Za-z0-9_-]{11})", url)
    if m:
        return {"platform": "youtube", "video_id": m.group(1)}
    return {"error": "Could not extract YouTube video_id"}


def _tiktok(url: str) -> dict:
    """Validate a TikTok URL and pass it through for downstream tools.

    TikTok doesn't expose a simple numeric id the way YouTube does, so this
    just recognizes standard "@user/video/<id>" URLs and short "vt./vm."
    links, returning the original URL for tools like `tiktok_comments` or
    `tiktok_video_info` to resolve directly.

    Args:
        url: A TikTok URL.

    Returns:
        {"platform": "tiktok", "url": url} (with a "note" for short links)
        on success, or {"error": ...} if the URL isn't recognized.
    """
    m = re.search("tiktok\\.com/@[^/]+/video/(\\d+)", url)
    if m:
        return {"platform": "tiktok", "url": url}
    if re.search("(vt|vm)\\.tiktok\\.com", url):
        return {
            "platform": "tiktok",
            "url": url,
            "note": "short link — use url directly for tiktok_comments/tiktok_video_info",
        }
    return {"error": "Could not extract TikTok video_id from URL"}
