import json
from typing import Any

from app.i18n import msg


def _clip(text: str, n: int = 48) -> str:
    """(Internal) Truncate text to at most `n` characters, appending an ellipsis if clipped.

    Args:
        text: (str) Text to truncate.
        n: (int, default 48) Maximum length before truncation.

    Returns:
        (str) The stripped text, or a shortened version ending in "…" if it exceeded `n` chars."""
    s = (text or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _ids(raw: Any) -> list[str]:
    """(Internal) Normalize a raw id list/CSV string into a clean list of id strings.

    Args:
        raw: (Any) Either a list of ids, a comma-separated string of ids, or anything else.

    Returns:
        (list[str]) Stripped, non-empty id strings; empty list if `raw` is
        neither a list nor a string."""
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str):
        return [x.strip() for x in raw.split(",") if x.strip()]
    return []


_NULLISH_STRINGS = {"null", "undefined", "none"}


def _drop_nullish_strings(value: Any) -> Any:
    """(Internal) Recursively blank out string values some models emit in place of
    an actual JSON null/missing field (e.g. a literal `"null"` string).

    Args:
        value: (Any) A parsed JSON value (dict/list/scalar).

    Returns:
        (Any) `value` with any `"null"`/`"undefined"`/`"none"`-like string leaves
        replaced by `None`, so downstream `.get(...) or default` fallbacks treat
        them as absent instead of rendering the literal word."""
    if isinstance(value, str):
        return None if value.strip().lower() in _NULLISH_STRINGS else value
    if isinstance(value, dict):
        return {k: _drop_nullish_strings(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_drop_nullish_strings(v) for v in value]
    return value


def _parse_args(arguments: str | None) -> dict:
    """(Internal) Parse a JSON-encoded tool call arguments string into a dict.

    Some models emit a literal `"null"` string instead of omitting an optional
    field or using real JSON null — those are sanitized to `None` here so they
    don't leak into status text (e.g. "Đang tìm video YouTube: «null»...").

    Args:
        arguments: (str | None) Raw JSON string of tool call arguments, or None.

    Returns:
        (dict) Parsed arguments dict, or an empty dict if `arguments` is falsy,
        not valid JSON, or does not decode to a dict."""
    if not arguments:
        return {}
    try:
        parsed = json.loads(arguments)
        return _drop_nullish_strings(parsed) if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def tool_status(tool: str, args: dict) -> str:
    """Localized tool progress detail for the current request locale (X-Lang)."""
    a = args or {}
    if tool == "youtube_search":
        q = _clip(a.get("keyword") or a.get("query") or "")
        return msg("agent.tool.youtube_search", q=q) if q else msg("agent.tool.youtube_search.generic")
    if tool == "youtube_get_comments":
        vid = a.get("video_id") or ""
        return msg("agent.tool.youtube_get_comments", vid=vid) if vid else msg("agent.tool.youtube_get_comments.generic")
    if tool == "youtube_get_comments_batch":
        ids = _ids(a.get("video_ids"))
        n = len(ids)
        if n == 1:
            return msg("agent.tool.youtube_get_comments_batch.one", id=ids[0])
        if n > 1:
            return msg("agent.tool.youtube_get_comments_batch.many", n=n, id=ids[0])
        return msg("agent.tool.youtube_get_comments_batch.generic")
    if tool in ("youtube_get_transcript",):
        vid = a.get("video_id") or ""
        return (
            msg("agent.tool.youtube_get_transcript", vid=vid)
            if vid
            else msg("agent.tool.youtube_get_transcript.generic")
        )
    if tool == "youtube_get_transcript_batch":
        ids = _ids(a.get("video_ids"))
        n = len(ids)
        if n == 1:
            return msg("agent.tool.youtube_get_transcript_batch.one", id=ids[0])
        if n > 1:
            return msg("agent.tool.youtube_get_transcript_batch.many", n=n, id=ids[0])
        return msg("agent.tool.youtube_get_transcript_batch.generic")
    if tool == "youtube_get_detail":
        vid = a.get("video_id") or ""
        return msg("agent.tool.youtube_get_detail", vid=vid) if vid else msg("agent.tool.youtube_get_detail.generic")
    if tool == "youtube_get_by_topic":
        topic = a.get("topic") or ""
        return (
            msg("agent.tool.youtube_get_by_topic", topic=topic)
            if topic
            else msg("agent.tool.youtube_get_by_topic.generic")
        )
    if tool == "youtube_get_by_region":
        q = _clip(a.get("query") or "")
        gl = a.get("gl") or ""
        return (
            msg("agent.tool.youtube_get_by_region", gl=gl, q=q)
            if q
            else msg("agent.tool.youtube_get_by_region.generic", gl=gl)
        )
    if tool == "youtube_get_channel_info":
        ch = _clip(a.get("channel_id") or "")
        return (
            msg("agent.tool.youtube_get_channel_info", ch=ch)
            if ch
            else msg("agent.tool.youtube_get_channel_info.generic")
        )
    if tool == "youtube_get_channel_videos":
        ch = _clip(a.get("channel_id") or "")
        return (
            msg("agent.tool.youtube_get_channel_videos", ch=ch)
            if ch
            else msg("agent.tool.youtube_get_channel_videos.generic")
        )
    if tool == "tiktok_search":
        q = _clip(a.get("keyword") or "")
        return msg("agent.tool.tiktok_search", q=q) if q else msg("agent.tool.tiktok_search.generic")
    if tool == "tiktok_comments":
        aweme = a.get("aweme_id") or ""
        return msg("agent.tool.tiktok_comments", aweme=aweme) if aweme else msg("agent.tool.tiktok_comments.generic")
    if tool == "tiktok_transcript":
        aweme = a.get("aweme_id") or ""
        return (
            msg("agent.tool.tiktok_transcript", aweme=aweme)
            if aweme
            else msg("agent.tool.tiktok_transcript.generic")
        )
    if tool == "tiktok_video_info":
        url = _clip(a.get("url") or "")
        return msg("agent.tool.tiktok_video_info.with_url") if url else msg("agent.tool.tiktok_video_info.no_url")
    if tool == "tiktok_profile":
        handle = a.get("handle") or ""
        return msg("agent.tool.tiktok_profile", handle=handle) if handle else msg("agent.tool.tiktok_profile.generic")
    if tool == "search_movie_summary":
        pid = _clip(a.get("movie_id") or "")
        return (
            msg("agent.tool.search_movie_summary", pid=pid)
            if pid
            else msg("agent.tool.search_movie_summary.generic")
        )
    if tool == "search_aspect_evidence":
        aspect = a.get("aspect") or ""
        pid = _clip(a.get("movie_id") or "")
        if aspect and pid:
            return msg("agent.tool.search_aspect_evidence", aspect=aspect, pid=pid)
        return msg("agent.tool.search_aspect_evidence.generic")
    if tool == "get_raw_reviews":
        pid = _clip(a.get("movie_id") or "")
        return msg("agent.tool.get_raw_reviews", pid=pid) if pid else msg("agent.tool.get_raw_reviews.generic")
    if tool == "extract_id_from_url":
        return msg("agent.tool.extract_id_from_url")
    return msg("agent.tool.default", tool=tool)
