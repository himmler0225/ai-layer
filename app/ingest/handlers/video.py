from app.repositories.search_cache import upsert_search_cache
from app.repositories.videos import upsert_video


async def handle_video_upsert(envelope: dict) -> None:
    """Upsert a video row and, if present, its associated search-cache entry.

    Args:
        envelope: Ingest envelope dict whose "payload" contains "video" (the
            normalized video dict) and optionally "search_cache" (query/platform/
            video_ids to cache for a search tool call).

    Returns:
        None. Does nothing if the payload has no "video".
    """
    payload = envelope.get("payload") or {}
    video = payload.get("video")
    if not video:
        return
    await upsert_video(
        id=video["id"],
        platform=video["platform"],
        title=video.get("title", ""),
        author=video.get("author", ""),
        views=video.get("views", 0),
        likes=video.get("likes", 0),
        comments_count=video.get("comments_count", 0),
        url=video.get("url", ""),
        transcript=video.get("transcript", ""),
        metadata=video.get("metadata"),
    )
    search = payload.get("search_cache")
    if search and search.get("query"):
        await upsert_search_cache(
            query=search["query"], platform=search["platform"], video_ids=search.get("video_ids") or []
        )
