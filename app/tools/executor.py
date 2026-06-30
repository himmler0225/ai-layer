from __future__ import annotations
from typing import Any, Dict
import jsonschema
import app.config.settings as settings
from app.clients import data_miner
from app.rag import search as rag_search
from app.services.url_extractor import extract_id_from_url as _url_extract
from app.tools.definitions import TIKTOK_TOOLS, UTIL_TOOLS, YOUTUBE_TOOLS
from app.tools.movie_definitions import MOVIE_TOOLS
from app.tools.rag_definitions import RAG_TOOLS
_RAG_TOOL_NAMES = frozenset((t['name'] for t in RAG_TOOLS))
_SCHEMAS: Dict[str, Dict] = {tool['name']: tool['parameters'] for tool in (*(RAG_TOOLS if settings.RAG_ENABLED else []), *YOUTUBE_TOOLS, *TIKTOK_TOOLS, *MOVIE_TOOLS, *UTIL_TOOLS)}

async def _youtube_search(inp: Dict) -> Any:
    """(Nội bộ) Youtube search (async).

    Args:
        inp: (Dict) Tham số `inp`.

    Returns:
        (Any) Kết quả trả về."""
    return await data_miner.search_youtube(query=inp['keyword'], max_results=inp.get('max_results', 5), sort=inp.get('sort', 'relevance'))

async def _youtube_get_by_topic(inp: Dict) -> Any:
    """(Nội bộ) Youtube get by topic (async).

    Args:
        inp: (Dict) Tham số `inp`.

    Returns:
        (Any) Kết quả trả về."""
    return await data_miner.get_by_topic(topic=inp['topic'], max_results=inp.get('max_results', 20))

async def _youtube_get_shorts(inp: Dict) -> Any:
    """(Nội bộ) Youtube get shorts (async).

    Args:
        inp: (Dict) Tham số `inp`.

    Returns:
        (Any) Kết quả trả về."""
    return await data_miner.get_shorts(max_results=inp.get('max_results', 20))

async def _youtube_get_live(inp: Dict) -> Any:
    """(Nội bộ) Youtube get live (async).

    Args:
        inp: (Dict) Tham số `inp`.

    Returns:
        (Any) Kết quả trả về."""
    return await data_miner.get_live(query=inp.get('query', ''), max_results=inp.get('max_results', 20))

async def _youtube_get_by_region(inp: Dict) -> Any:
    """(Nội bộ) Youtube get by region (async).

    Args:
        inp: (Dict) Tham số `inp`.

    Returns:
        (Any) Kết quả trả về."""
    return await data_miner.get_by_region(gl=inp['gl'], hl=inp.get('hl', 'vi'), query=inp['query'], max_results=inp.get('max_results', 20))

async def _youtube_get_detail(inp: Dict) -> Any:
    """(Nội bộ) Youtube get detail (async).

    Args:
        inp: (Dict) Tham số `inp`.

    Returns:
        (Any) Kết quả trả về."""
    return await data_miner.get_video_detail(inp['video_id'])

async def _youtube_get_comments(inp: Dict) -> Any:
    """(Nội bộ) Youtube get comments (async).

    Args:
        inp: (Dict) Tham số `inp`.

    Returns:
        (Any) Kết quả trả về."""
    return await data_miner.get_video_comments(video_id=inp['video_id'], max_comments=inp.get('max_comments', settings.AGENT_MAX_COMMENTS), sort=inp.get('sort', 'top'))

async def _youtube_get_comments_batch(inp: Dict) -> Any:
    """(Nội bộ) Youtube get comments batch (async).

    Args:
        inp: (Dict) Tham số `inp`.

    Returns:
        (Any) Kết quả trả về."""
    raw = inp.get('video_ids', [])
    if isinstance(raw, str):
        ids = [v.strip() for v in raw.split(',') if v.strip()]
    else:
        ids = [str(v).strip() for v in raw if str(v).strip()]
    sort = inp.get('sort', 'top')
    if sort not in ('top', 'newest'):
        sort = 'top'
    return await data_miner.get_video_comments_batch(video_ids=ids[:8], max_per_video=inp.get('max_per_video', settings.AGENT_MAX_COMMENTS), sort=sort)

async def _youtube_get_transcript(inp: Dict) -> Any:
    """(Nội bộ) Youtube get transcript (async).

    Args:
        inp: (Dict) Tham số `inp`.

    Returns:
        (Any) Kết quả trả về."""
    return await data_miner.get_video_transcript(inp['video_id'])

async def _youtube_get_transcript_batch(inp: Dict) -> Any:
    """(Nội bộ) Youtube get transcript batch (async).

    Args:
        inp: (Dict) Tham số `inp`.

    Returns:
        (Any) Kết quả trả về."""
    raw = inp.get('video_ids', [])
    if isinstance(raw, str):
        ids = [v.strip() for v in raw.split(',') if v.strip()]
    else:
        ids = [str(v).strip() for v in raw if str(v).strip()]
    return await data_miner.get_video_transcript_batch(ids[:8])

async def _youtube_get_channel_info(inp: Dict) -> Any:
    """(Nội bộ) Youtube get channel info (async).

    Args:
        inp: (Dict) Tham số `inp`.

    Returns:
        (Any) Kết quả trả về."""
    return await data_miner.get_channel_info(inp['channel_id'])

async def _youtube_get_channel_videos(inp: Dict) -> Any:
    """(Nội bộ) Youtube get channel videos (async).

    Args:
        inp: (Dict) Tham số `inp`.

    Returns:
        (Any) Kết quả trả về."""
    return await data_miner.get_channel_videos(channel_id=inp['channel_id'], max_results=inp.get('max_results', 30))

async def _youtube_get_channel_playlists(inp: Dict) -> Any:
    """(Nội bộ) Youtube get channel playlists (async).

    Args:
        inp: (Dict) Tham số `inp`.

    Returns:
        (Any) Kết quả trả về."""
    return await data_miner.get_channel_playlists(inp['channel_id'])

async def _youtube_get_playlist_videos(inp: Dict) -> Any:
    """(Nội bộ) Youtube get playlist videos (async).

    Args:
        inp: (Dict) Tham số `inp`.

    Returns:
        (Any) Kết quả trả về."""
    return await data_miner.get_playlist_videos(playlist_id=inp['playlist_id'], max_results=inp.get('max_results', 30))

async def _tiktok_search(inp: Dict) -> Any:
    """(Nội bộ) Tiktok search (async).

    Args:
        inp: (Dict) Tham số `inp`.

    Returns:
        (Any) Kết quả trả về."""
    return await data_miner.tiktok_search(keyword=inp['keyword'], cursor=inp.get('cursor', 0), sort_by=inp.get('sort_by'), date_posted=inp.get('date_posted'), region=inp.get('region'))

async def _tiktok_video_info(inp: Dict) -> Any:
    """(Nội bộ) Tiktok video info (async).

    Args:
        inp: (Dict) Tham số `inp`.

    Returns:
        (Any) Kết quả trả về."""
    return await data_miner.tiktok_video_info(url=inp['url'])

async def _tiktok_comments(inp: Dict) -> Any:
    """(Nội bộ) Tiktok comments (async).

    Args:
        inp: (Dict) Tham số `inp`.

    Returns:
        (Any) Kết quả trả về."""
    return await data_miner.tiktok_comments(aweme_id=inp['aweme_id'], cursor=inp.get('cursor', 0), count=inp.get('count', 20))

async def _tiktok_profile(inp: Dict) -> Any:
    """(Nội bộ) Tiktok profile (async).

    Args:
        inp: (Dict) Tham số `inp`.

    Returns:
        (Any) Kết quả trả về."""
    return await data_miner.tiktok_profile(inp['handle'])

async def _tiktok_transcript(inp: Dict) -> Any:
    """(Nội bộ) Tiktok transcript (async).

    Args:
        inp: (Dict) Tham số `inp`.

    Returns:
        (Any) Kết quả trả về."""
    return await data_miner.tiktok_transcript(aweme_id=inp['aweme_id'])

async def _extract_id_from_url(inp: Dict) -> Any:
    """(Nội bộ) Trích xuất id from url (async).

    Args:
        inp: (Dict) Tham số `inp`.

    Returns:
        (Any) Kết quả trả về."""
    return _url_extract(url=inp['url'])

async def _movie_search(inp: Dict) -> Any:
    return await data_miner.movie_search(
        inp['keyword'],
        provider=inp.get('provider'),
        page=inp.get('page', 1),
        limit=inp.get('limit', 10),
    )

async def _movie_get_detail(inp: Dict) -> Any:
    return await data_miner.movie_get_detail(inp['slug'], provider=inp.get('provider'))

async def _movie_list_new(inp: Dict) -> Any:
    return await data_miner.movie_list_new(provider=inp.get('provider'), page=inp.get('page', 1))

async def _movie_list_by_type(inp: Dict) -> Any:
    return await data_miner.movie_list_by_type(
        inp['type'],
        provider=inp.get('provider'),
        page=inp.get('page', 1),
        limit=inp.get('limit', 10),
        category=inp.get('category'),
        country=inp.get('country'),
        year=inp.get('year'),
        sort_lang=inp.get('sort_lang'),
        sort_field=inp.get('sort_field'),
        sort_type=inp.get('sort_type'),
    )

async def _movie_list_by_genre(inp: Dict) -> Any:
    return await data_miner.movie_list_by_genre(
        inp['slug'],
        provider=inp.get('provider'),
        page=inp.get('page', 1),
        limit=inp.get('limit', 10),
        category=inp.get('category'),
        country=inp.get('country'),
        year=inp.get('year'),
        sort_lang=inp.get('sort_lang'),
        sort_field=inp.get('sort_field'),
        sort_type=inp.get('sort_type'),
    )

async def _movie_list_by_country(inp: Dict) -> Any:
    return await data_miner.movie_list_by_country(
        inp['slug'],
        provider=inp.get('provider'),
        page=inp.get('page', 1),
        limit=inp.get('limit', 10),
        category=inp.get('category'),
        country=inp.get('country'),
        year=inp.get('year'),
        sort_lang=inp.get('sort_lang'),
        sort_field=inp.get('sort_field'),
        sort_type=inp.get('sort_type'),
    )

async def _movie_list_by_year(inp: Dict) -> Any:
    return await data_miner.movie_list_by_year(
        inp['year'],
        provider=inp.get('provider'),
        page=inp.get('page', 1),
        limit=inp.get('limit', 10),
        category=inp.get('category'),
        country=inp.get('country'),
        sort_lang=inp.get('sort_lang'),
        sort_field=inp.get('sort_field'),
        sort_type=inp.get('sort_type'),
    )

async def _movie_get_metadata(inp: Dict) -> Any:
    provider = inp.get('provider')
    if inp['kind'] == 'genres':
        return await data_miner.movie_get_genres(provider=provider)
    return await data_miner.movie_get_countries(provider=provider)

_REGISTRY = {'youtube_search': _youtube_search, 'youtube_get_by_topic': _youtube_get_by_topic, 'youtube_get_shorts': _youtube_get_shorts, 'youtube_get_live': _youtube_get_live, 'youtube_get_by_region': _youtube_get_by_region, 'youtube_get_detail': _youtube_get_detail, 'youtube_get_comments': _youtube_get_comments, 'youtube_get_comments_batch': _youtube_get_comments_batch, 'youtube_get_transcript': _youtube_get_transcript, 'youtube_get_transcript_batch': _youtube_get_transcript_batch, 'youtube_get_channel_info': _youtube_get_channel_info, 'youtube_get_channel_videos': _youtube_get_channel_videos, 'youtube_get_channel_playlists': _youtube_get_channel_playlists, 'youtube_get_playlist_videos': _youtube_get_playlist_videos, 'tiktok_search': _tiktok_search, 'tiktok_video_info': _tiktok_video_info, 'tiktok_comments': _tiktok_comments, 'tiktok_profile': _tiktok_profile, 'tiktok_transcript': _tiktok_transcript, 'extract_id_from_url': _extract_id_from_url, 'movie_search': _movie_search, 'movie_get_detail': _movie_get_detail, 'movie_list_new': _movie_list_new, 'movie_list_by_type': _movie_list_by_type, 'movie_list_by_genre': _movie_list_by_genre, 'movie_list_by_country': _movie_list_by_country, 'movie_list_by_year': _movie_list_by_year, 'movie_get_metadata': _movie_get_metadata}

async def execute_tool(name: str, inputs: Dict, **kwargs) -> Dict:
    """Thực thi tool (async).

    Args:
        name: (str) Tham số `name`.
        inputs: (Dict) Tham số `inputs`.
        kwargs: (Any) Tham số `kwargs`.

    Returns:
        (Dict) Kết quả trả về."""
    schema = _SCHEMAS.get(name)
    if schema:
        try:
            jsonschema.validate(instance=inputs, schema=schema)
        except jsonschema.ValidationError as e:
            return {'error': f'Invalid input for {name}: {e.message}'}
    if name in _RAG_TOOL_NAMES:
        if not settings.RAG_ENABLED:
            return {'error': 'RAG disabled'}
        if name == 'search_movie_summary':
            return await rag_search.search_aspect_summary(inputs['movie_id'], inputs['query'], aspect=inputs.get('aspect'))
        if name == 'search_aspect_evidence':
            return await rag_search.search_aspect_evidence(inputs['movie_id'], inputs['query'], aspect=inputs.get('aspect'))
        if name == 'get_raw_reviews':
            return await rag_search.get_raw_reviews(inputs['movie_id'], limit=int(inputs.get('limit') or 10))
    fn = _REGISTRY.get(name)
    if fn is None:
        return {'error': f'Unknown tool: {name}'}
    try:
        result = await fn(inputs)
        if isinstance(result, dict):
            if result.get('success') is True and isinstance(result.get('data'), (dict, list)):
                result = result['data']
            elif result.get('success') is False:
                return {
                    'error': result.get('error') or 'data-miner request failed',
                    'tool': name,
                }
        return result if isinstance(result, dict) else {'data': result}
    except Exception as e:
        return {'error': str(e), 'tool': name}
