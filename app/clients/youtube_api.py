import httpx
from typing import Dict, Optional
from app.config.settings import YOUTUBE_API_URL, YOUTUBE_API_KEY

_HEADERS = {"Authorization": f"Bearer {YOUTUBE_API_KEY}"}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=YOUTUBE_API_URL, headers=_HEADERS, timeout=15)


async def list_videos(query: Optional[str] = None, page: int = 1, limit: int = 20) -> Dict:
    params: Dict = {"page": page, "limit": limit}
    if query:
        params["q"] = query
    async with _client() as c:
        r = await c.get("/videos", params=params)
        r.raise_for_status()
        return r.json()


async def get_video(video_id: str) -> Dict:
    async with _client() as c:
        r = await c.get(f"/videos/{video_id}")
        r.raise_for_status()
        return r.json()


async def get_trending_videos(limit: int = 20) -> Dict:
    async with _client() as c:
        r = await c.get("/videos/trending", params={"limit": limit})
        r.raise_for_status()
        return r.json()
