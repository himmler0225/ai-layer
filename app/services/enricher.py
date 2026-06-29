from typing import Dict, List, Optional, Tuple
from urllib.parse import quote
from app.rag.product_hint import extract_product_name
from .review_summarizer import summarize_reviews
_HISTORY_MARKER = '\n[Câu hỏi hiện tại]\n'
_MAX_UI_VIDEOS = 8

def _youtube_url(video_id: str) -> str:
    return f'https://www.youtube.com/watch?v={video_id}'

def _youtube_search_url(query: str) -> str:
    return f'https://www.youtube.com/results?search_query={quote(query)}'

def _tiktok_url(aweme_id: str) -> str:
    return f'https://www.tiktok.com/@_/video/{aweme_id}'

def _best_thumb(thumbnails, video_id: str='') -> Optional[str]:
    if isinstance(thumbnails, list):
        for t in reversed(thumbnails):
            if isinstance(t, dict):
                url = t.get('url', '')
                if url:
                    if url.startswith('//'):
                        url = 'https:' + url
                    return url
    if video_id:
        return f'https://i.ytimg.com/vi/{video_id}/hqdefault.jpg'
    return None

def _safe(item) -> Optional[Dict]:
    return item if isinstance(item, dict) else None

def _fmt_views(views) -> Optional[str]:
    try:
        n = int(views)
        if n >= 1000000:
            return f'{n / 1000000:.1f}M views'
        if n >= 1000:
            return f'{n // 1000}K views'
        return f'{n} views'
    except (TypeError, ValueError):
        return str(views) if views else None

def _unwrap(result) -> dict:
    if isinstance(result, dict) and 'success' in result and ('data' in result):
        inner = result.get('data')
        if isinstance(inner, (dict, list)):
            return inner if isinstance(inner, dict) else {'_list': inner}
    return result if isinstance(result, dict) else {}

def _detect_source_label(tool_calls: List[Dict]) -> str:
    has_youtube = any((c.get('tool', '').startswith('youtube_') for c in tool_calls))
    has_tiktok = any((c.get('tool', '').startswith('tiktok_') for c in tool_calls))
    if has_youtube and has_tiktok:
        return 'YouTube & TikTok'
    if has_tiktok:
        return 'TikTok'
    if has_youtube:
        return 'YouTube'
    return 'đa nguồn'

def _review_entry(content: str, *, platform: str, source_url: Optional[str]=None) -> Dict:
    return {'content': content, 'source_url': source_url, 'platform': platform}

def _youtube_video_entry(v: dict, vid: str) -> Dict:
    url = _youtube_url(vid)
    thumb = _best_thumb(v.get('thumbnails', []) or [], vid)
    return {'video_id': vid, 'title': v.get('title'), 'channel': v.get('channel') or v.get('author'), 'views': v.get('view_count') or v.get('views'), 'thumbnail': thumb, 'source_url': url, 'platform': 'youtube'}

def _collect_all(tool_calls: List[Dict]) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    seen_urls: set = set()
    all_reviews: List[Dict] = []
    sources: List[Dict] = []
    search_catalog: Dict[str, Dict] = {}
    analyzed_keys: List[str] = []
    video_by_key: Dict[str, Dict] = {}

    def _add_source(label: str, url: str, kind: str, **meta):
        if url and url not in seen_urls:
            seen_urls.add(url)
            source = {'label': label[:80], 'url': url, 'type': kind}
            source.update({k: v for k, v in meta.items() if v is not None})
            sources.append(source)

    def _mark_analyzed(entry: Dict, key: str) -> None:
        if key not in video_by_key:
            analyzed_keys.append(key)
        video_by_key[key] = entry
    for call in tool_calls:
        tool = call.get('tool', '')
        inputs = call.get('inputs', {})
        result = _unwrap(call.get('result', {}))
        if not isinstance(result, dict):
            continue
        if tool == 'youtube_search':
            q = inputs.get('keyword') or inputs.get('query', '')
            _add_source(f'YouTube: "{q}"', _youtube_search_url(q), 'search', platform='youtube')
            video_list = result.get('_list') or result.get('results') or result.get('videos') or []
            for raw_v in video_list:
                v = _safe(raw_v)
                if v and v.get('video_id'):
                    search_catalog[v['video_id']] = v
        elif tool == 'youtube_get_detail':
            vid = result.get('video_id') or inputs.get('video_id')
            if vid:
                entry = _youtube_video_entry({'title': result.get('title'), 'channel': result.get('author') or result.get('channel'), 'view_count': result.get('views') or result.get('view_count'), 'thumbnails': result.get('thumbnails', []) or result.get('thumbnail', [])}, vid)
                entry['duration'] = result.get('length_seconds')
                entry['description'] = (result.get('description') or '')[:300]
                _mark_analyzed(entry, f'yt:{vid}')
                _add_source((result.get('title') or vid)[:80], _youtube_url(vid), 'video', thumbnail=entry.get('thumbnail'), channel=entry.get('channel'), views=_fmt_views(entry.get('views')), platform='youtube')
        elif tool in ('youtube_get_comments', 'youtube_get_transcript'):
            vid = inputs.get('video_id')
            url = _youtube_url(vid) if vid else None
            for raw_c in result.get('comments') or result.get('_list') or []:
                c = _safe(raw_c)
                if c:
                    text = c.get('content') or c.get('text') or ''
                    if text:
                        all_reviews.append(_review_entry(text, platform='youtube', source_url=url))
            if vid:
                cat = search_catalog.get(vid, {})
                _mark_analyzed(_youtube_video_entry(cat, vid), f'yt:{vid}')
                if url:
                    _add_source(f'YouTube: {vid}', url, 'reviews', platform='youtube')
        elif tool in ('youtube_get_comments_batch', 'youtube_get_transcript_batch'):
            for raw_vr in result.get('results') or result.get('_list') or []:
                vid_result = _safe(raw_vr)
                if not vid_result:
                    continue
                vid = vid_result.get('video_id')
                url = _youtube_url(vid) if vid else None
                for raw_c in vid_result.get('comments') or vid_result.get('segments') or []:
                    c = _safe(raw_c)
                    if c:
                        text = c.get('content') or c.get('text') or ''
                        if text:
                            all_reviews.append(_review_entry(text, platform='youtube', source_url=url))
                if vid:
                    cat = search_catalog.get(vid, {})
                    entry = _youtube_video_entry({**cat, 'title': cat.get('title') or vid_result.get('title'), 'channel': cat.get('channel') or vid_result.get('channel'), 'view_count': cat.get('view_count') or vid_result.get('view_count')}, vid)
                    _mark_analyzed(entry, f'yt:{vid}')
                    if url and (vid_result.get('comments') or vid_result.get('segments')):
                        _add_source(f'YouTube: {vid}', url, 'reviews', platform='youtube')
        elif tool == 'tiktok_search':
            q = inputs.get('keyword', '')
            _add_source(f'TikTok: "{q}"', f'https://www.tiktok.com/search?q={quote(q)}', 'search', platform='tiktok')
            for raw_v in result.get('videos') or result.get('items') or result.get('_list') or []:
                v = _safe(raw_v)
                if v:
                    aweme = str(v.get('aweme_id') or v.get('id') or '')
                    if aweme:
                        search_catalog[f'tt:{aweme}'] = v
        elif tool in ('tiktok_comments', 'tiktok_transcript'):
            aweme_id = str(inputs.get('aweme_id') or '')
            url = inputs.get('url') or (_tiktok_url(aweme_id) if aweme_id else '')
            items = result.get('comments') or result.get('segments') or []
            for raw_c in items:
                c = _safe(raw_c)
                if c:
                    text = c.get('content') or c.get('text') or ''
                elif isinstance(raw_c, str):
                    text = raw_c
                else:
                    continue
                if text:
                    all_reviews.append(_review_entry(text, platform='tiktok', source_url=url))
            if aweme_id:
                cat = search_catalog.get(f'tt:{aweme_id}', {})
                title = cat.get('desc') or cat.get('title') or aweme_id
                author = (cat.get('author') or {}).get('nickname') or cat.get('author_name', '')
                plays = (cat.get('statistics') or {}).get('play_count') or cat.get('play_count')
                cover = cat.get('video', {}).get('cover', {}).get('url_list', [])
                thumb = cover[0] if cover else None
                _mark_analyzed({'video_id': aweme_id, 'title': title, 'channel': author, 'views': plays, 'thumbnail': thumb, 'source_url': url, 'platform': 'tiktok'}, f'tt:{aweme_id}')
                if url:
                    _add_source(f'TikTok: {url[-20:]}', url, 'reviews', platform='tiktok')
        elif tool == 'tiktok_video_info':
            url = inputs.get('url', '')
            v = result
            aweme = str(v.get('aweme_id') or v.get('id') or '')
            title = v.get('desc') or v.get('title') or aweme
            author = (v.get('author') or {}).get('nickname') or ''
            plays = (v.get('statistics') or {}).get('play_count')
            cover = v.get('video', {}).get('cover', {}).get('url_list', [])
            thumb = cover[0] if cover else None
            if aweme:
                _mark_analyzed({'video_id': aweme, 'title': title, 'channel': author, 'views': plays, 'thumbnail': thumb, 'source_url': url, 'platform': 'tiktok'}, f'tt:{aweme}')
            if url:
                _add_source(title[:80], url, 'video', thumbnail=thumb, channel=author, views=_fmt_views(plays), platform='tiktok')
    all_videos = [video_by_key[k] for k in analyzed_keys if k in video_by_key]
    all_videos.sort(key=lambda v: int(v.get('views') or 0), reverse=True)
    all_videos = all_videos[:_MAX_UI_VIDEOS]
    return (all_reviews, all_videos, sources)

def _product_name(task: str, videos: List[Dict]) -> str:
    from_block = extract_product_name(task)
    if from_block:
        return from_block
    question = task.split(_HISTORY_MARKER)[-1].strip() if task else ''
    for prefix in ('review ', 'đánh giá ', 'tìm hiểu ', 'phân tích '):
        if question.lower().startswith(prefix):
            question = question[len(prefix):].strip()
    if question and len(question) <= 80:
        return question
    if videos:
        return (videos[0].get('title') or 'sản phẩm')[:80]
    return 'sản phẩm'

async def enrich_agent_result(result_text: str, tool_calls: List[Dict], iterations: int, task: str='', *, include_summary: bool=True) -> Dict:
    all_reviews, all_videos, sources = _collect_all(tool_calls)
    source_label = _detect_source_label(tool_calls)
    product = _product_name(task, all_videos)
    review_summary = None
    if include_summary and all_reviews:
        review_summary = await summarize_reviews(all_reviews, product=product, source=source_label, task=task)
    return {'result': result_text, 'data': {'review_summary': review_summary, 'sources': sources, 'videos': all_videos, 'reviews_analyzed': len(all_reviews), 'review_source': source_label}, 'tool_calls': [{'tool': c['tool'], 'inputs': c['inputs']} for c in tool_calls], 'iterations': iterations}
