from __future__ import annotations
import asyncio
from typing import Any, Dict, Optional
import httpx
import app.config.settings as settings
from app.config.constants import DATA_MINER_MAX_CONN, DATA_MINER_MAX_KEEPALIVE, HTTP_MAX_ATTEMPTS, HTTP_RETRY_STATUSES
from app.config.headers import get_data_miner_headers
from app.config.logger import Logger
from app.exceptions import AiLayerUpstreamError
logger = Logger.get(__name__)
_MAX_ATTEMPTS = HTTP_MAX_ATTEMPTS
_RETRY_ON_STATUS = HTTP_RETRY_STATUSES
_client: Optional[httpx.AsyncClient] = None


def _headers() -> Dict[str, str]:
    """(Nội bộ) Headers `_headers`.

    Returns:
        (Dict[str, str]) Kết quả trả về."""
    return get_data_miner_headers(
        settings.DATA_MINER_KEY,
        settings.DATA_MINER_SERVICE_TOKEN,
    )


def _get_client() -> httpx.AsyncClient:
    """(Nội bộ) Lấy client.

    Returns:
        (httpx.AsyncClient) Kết quả trả về."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=settings.DATA_MINER_URL,
            headers=_headers(),
            timeout=settings.DATA_MINER_TIMEOUT,
            limits=httpx.Limits(
                max_connections=DATA_MINER_MAX_CONN,
                max_keepalive_connections=DATA_MINER_MAX_KEEPALIVE,
            ),
        )
    return _client

async def close_client() -> None:
    """Đóng client (async).

    Returns:
        (None) Kết quả trả về."""
    global _client
    if _client and (not _client.is_closed):
        await _client.aclose()
        _client = None

async def _get(path: str, params: Dict=None) -> Any:
    """(Nội bộ) Lấy `_get` (async).

    Args:
        path: (str) Tham số `path`.
        params: (Dict, mặc định None) Tham số `params`.

    Returns:
        (Any) Kết quả trả về."""
    last_exc: Exception = AiLayerUpstreamError('Unknown error')
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            r = await _get_client().get(path, params=params or {}, headers=_headers())
            if r.status_code in _RETRY_ON_STATUS:
                raise httpx.HTTPStatusError(f'{r.status_code} from data-miner', request=r.request, response=r)
            r.raise_for_status()
            return r.json()
        except (httpx.NetworkError, httpx.TimeoutException) as e:
            last_exc = e
        except httpx.HTTPStatusError as e:
            if e.response.status_code not in _RETRY_ON_STATUS:
                raise
            last_exc = e
        if attempt < _MAX_ATTEMPTS:
            delay = 2 ** (attempt - 1)
            logger.warning('[data_miner] GET %s retry=%d/%d delay=%ds', path, attempt, _MAX_ATTEMPTS, delay)
            await asyncio.sleep(delay)
        else:
            logger.error('[data_miner] GET %s failed attempts=%d', path, _MAX_ATTEMPTS)
    raise AiLayerUpstreamError(str(last_exc), cause=last_exc) from last_exc

async def search_youtube(query: str, max_results: int=10, sort: str='relevance') -> Dict:
    """Tìm kiếm youtube (async).

    Args:
        query: (str) Tham số `query`.
        max_results: (int, mặc định 10) Tham số `max_results`.
        sort: (str, mặc định 'relevance') Tham số `sort`.

    Returns:
        (Dict) Kết quả trả về."""
    return await _get('/api/videos/search', {'q': query, 'max_results': max_results, 'sort': sort})

async def get_video_detail(video_id: str) -> Dict:
    """Lấy video detail (async).

    Args:
        video_id: (str) Tham số `video_id`.

    Returns:
        (Dict) Kết quả trả về."""
    return await _get(f'/api/videos/{video_id}')

async def get_video_comments(video_id: str, max_comments: int=20, sort: str='newest') -> Dict:
    """Lấy video comments (async).

    Args:
        video_id: (str) Tham số `video_id`.
        max_comments: (int, mặc định 20) Tham số `max_comments`.
        sort: (str, mặc định 'newest') Tham số `sort`.

    Returns:
        (Dict) Kết quả trả về."""
    return await _get(f'/api/videos/{video_id}/comments', {'limit': max_comments, 'sort': sort})

async def get_video_comments_batch(video_ids: list, max_per_video: int=20, sort: str='top') -> Dict:
    """Lấy video comments batch (async).

    Args:
        video_ids: (list) Tham số `video_ids`.
        max_per_video: (int, mặc định 20) Tham số `max_per_video`.
        sort: (str, mặc định 'top') Tham số `sort`.

    Returns:
        (Dict) Kết quả trả về."""
    return await _get('/api/videos/comments/batch', {'video_ids': ','.join(video_ids), 'limit': max_per_video, 'sort': sort})

async def get_video_transcript(video_id: str) -> Dict:
    """Lấy video transcript (async).

    Args:
        video_id: (str) Tham số `video_id`.

    Returns:
        (Dict) Kết quả trả về."""
    return await _get(f'/api/videos/{video_id}/transcript')

async def get_video_transcript_batch(video_ids: list) -> Dict:
    """Lấy video transcript batch (async).

    Args:
        video_ids: (list) Tham số `video_ids`.

    Returns:
        (Dict) Kết quả trả về."""
    return await _get('/api/videos/transcript/batch', {'video_ids': ','.join(video_ids)})

async def get_trending(max_results: int=20) -> Dict:
    """Lấy trending (async).

    Args:
        max_results: (int, mặc định 20) Tham số `max_results`.

    Returns:
        (Dict) Kết quả trả về."""
    return await _get('/api/videos/trending', {'limit': max_results})

async def get_shorts(max_results: int=20) -> Dict:
    """Lấy shorts (async).

    Args:
        max_results: (int, mặc định 20) Tham số `max_results`.

    Returns:
        (Dict) Kết quả trả về."""
    return await _get('/api/videos/shorts', {'limit': max_results})

async def get_live(query: str='', max_results: int=20) -> Dict:
    """Lấy live (async).

    Args:
        query: (str, mặc định '') Tham số `query`.
        max_results: (int, mặc định 20) Tham số `max_results`.

    Returns:
        (Dict) Kết quả trả về."""
    return await _get('/api/videos/live', {'q': query, 'limit': max_results})

async def get_by_region(gl: str, hl: str, query: str, max_results: int=20) -> Dict:
    """Lấy by region (async).

    Args:
        gl: (str) Tham số `gl`.
        hl: (str) Tham số `hl`.
        query: (str) Tham số `query`.
        max_results: (int, mặc định 20) Tham số `max_results`.

    Returns:
        (Dict) Kết quả trả về."""
    return await _get('/api/videos/location', {'gl': gl, 'hl': hl, 'query': query, 'max_results': max_results})

async def get_by_topic(topic: str, max_results: int=20) -> Dict:
    """Lấy by topic (async).

    Args:
        topic: (str) Tham số `topic`.
        max_results: (int, mặc định 20) Tham số `max_results`.

    Returns:
        (Dict) Kết quả trả về."""
    return await _get('/api/videos/by-topic', {'topic': topic, 'limit': max_results})

async def get_channel_info(channel_id: str) -> Dict:
    """Lấy channel info (async).

    Args:
        channel_id: (str) Tham số `channel_id`.

    Returns:
        (Dict) Kết quả trả về."""
    return await _get(f'/api/channels/{channel_id}')

async def get_channel_videos(channel_id: str, max_results: int=30) -> Dict:
    """Lấy channel videos (async).

    Args:
        channel_id: (str) Tham số `channel_id`.
        max_results: (int, mặc định 30) Tham số `max_results`.

    Returns:
        (Dict) Kết quả trả về."""
    return await _get(f'/api/channels/{channel_id}/videos', {'limit': max_results})

async def get_channel_playlists(channel_id: str) -> Dict:
    """Lấy channel playlists (async).

    Args:
        channel_id: (str) Tham số `channel_id`.

    Returns:
        (Dict) Kết quả trả về."""
    return await _get(f'/api/channels/{channel_id}/playlists')

async def get_playlist_videos(playlist_id: str, max_results: int=30) -> Dict:
    """Lấy playlist videos (async).

    Args:
        playlist_id: (str) Tham số `playlist_id`.
        max_results: (int, mặc định 30) Tham số `max_results`.

    Returns:
        (Dict) Kết quả trả về."""
    return await _get(f'/api/playlists/{playlist_id}/videos', {'limit': max_results})

async def tiktok_search(keyword: str, cursor: int=0, sort_by: str=None, date_posted: str=None, region: str=None) -> Dict:
    """Tiktok search (async).

    Args:
        keyword: (str) Tham số `keyword`.
        cursor: (int, mặc định 0) Tham số `cursor`.
        sort_by: (str, mặc định None) Tham số `sort_by`.
        date_posted: (str, mặc định None) Tham số `date_posted`.
        region: (str, mặc định None) Tham số `region`.

    Returns:
        (Dict) Kết quả trả về."""
    params: Dict = {'q': keyword, 'cursor': cursor}
    if sort_by:
        params['sort_by'] = sort_by
    if date_posted:
        params['date_posted'] = date_posted
    if region:
        params['region'] = region
    return await _get('/api/tiktok/search', params)

async def tiktok_video_info(url: str) -> Dict:
    """Tiktok video info (async).

    Args:
        url: (str) Tham số `url`.

    Returns:
        (Dict) Kết quả trả về."""
    return await _get('/api/tiktok/video-info', {'url': url})

async def tiktok_comments(aweme_id: str, cursor: int=0, count: int=20) -> Dict:
    """Tiktok comments (async).

    Args:
        aweme_id: (str) Tham số `aweme_id`.
        cursor: (int, mặc định 0) Tham số `cursor`.
        count: (int, mặc định 20) Tham số `count`.

    Returns:
        (Dict) Kết quả trả về."""
    return await _get('/api/tiktok/comments', {'aweme_id': aweme_id, 'cursor': cursor, 'count': count})

async def tiktok_profile(handle: str) -> Dict:
    """Tiktok profile (async).

    Args:
        handle: (str) Tham số `handle`.

    Returns:
        (Dict) Kết quả trả về."""
    return await _get(f'/api/tiktok/profiles/{handle}')

async def tiktok_transcript(aweme_id: str) -> Dict:
    """Tiktok transcript (async).

    Args:
        aweme_id: (str) Tham số `aweme_id`.

    Returns:
        (Dict) Kết quả trả về."""
    return await _get('/api/tiktok/transcript', {'aweme_id': aweme_id})
