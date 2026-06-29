from __future__ import annotations
from app.repositories.search_cache import upsert_search_cache
from app.repositories.videos import upsert_video

async def handle_video_upsert(envelope: dict) -> None:
    """Xử lý video upsert (async).

    Args:
        envelope: (dict) Tham số `envelope`.

    Returns:
        (None) Kết quả trả về."""
    payload = envelope.get('payload') or {}
    video = payload.get('video')
    if not video:
        return
    await upsert_video(id=video['id'], platform=video['platform'], title=video.get('title', ''), author=video.get('author', ''), views=video.get('views', 0), likes=video.get('likes', 0), comments_count=video.get('comments_count', 0), url=video.get('url', ''), transcript=video.get('transcript', ''), metadata=video.get('metadata'))
    search = payload.get('search_cache')
    if search and search.get('query'):
        await upsert_search_cache(query=search['query'], platform=search['platform'], video_ids=search.get('video_ids') or [])
