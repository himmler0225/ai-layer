from __future__ import annotations
import json
import app.config.settings as settings
from app.ai.router import TASK_ASPECT_GROUP, TASK_ASPECT_SUMMARY, max_tokens_for_task
from app.config.logger import Logger
from app.ingest.processing.embeddings import embed_texts
from app.repositories.aspect_chunks import delete_aspect_chunks_for_movie, upsert_aspect_chunks
from app.repositories.aspect_summaries import upsert_aspect_summary
from app.repositories.curated_reviews import get_curated_reviews
from app.repositories.movies import get_movie, upsert_movie
from app.repositories.raw_reviews import count_raw_reviews
from app.services import prompts as rag_prompts
from app.utils.openai_responses import complete_json
logger = Logger.get(__name__)
ASPECTS = ['battery', 'camera', 'screen', 'performance', 'design', 'price', 'software', 'durability', 'other']
_MAX_CURATED_FOR_LLM = 200

def _parse_json(raw: str) -> dict | list | None:
    """(Nội bộ) Phân tích json.

    Args:
        raw: (str) Tham số `raw`.

    Returns:
        (dict | list | None) Kết quả trả về."""
    text = (raw or '').strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None

def _fallback_group(curated: list[dict]) -> list[dict]:
    """(Nội bộ) Fallback group.

    Args:
        curated: (list[dict]) Tham số `curated`.

    Returns:
        (list[dict]) Kết quả trả về."""
    texts = [c['content'] for c in curated[:50]]
    return [{'aspect': 'other', 'review_ids': [c.get('raw_review_id') for c in curated[:50]], 'content': '\n'.join(texts), 'positive_percent': 70.0, 'negative_percent': 30.0}]

async def _llm_group_aspects(curated: list[dict], *, movie_name: str) -> list[dict]:
    """(Nội bộ) Llm group aspects (async).

    Args:
        curated: (list[dict]) Tham số `curated`.
        movie_name: (str) Tham số `movie_name`.

    Returns:
        (list[dict]) Kết quả trả về."""
    if not curated:
        return []
    lines = []
    for c in curated[:_MAX_CURATED_FOR_LLM]:
        rid = c.get('raw_review_id') or c.get('id', '')
        likes = c.get('likes', 0)
        content = (c.get('content') or '')[:500]
        lines.append(f'- id={rid} likes={likes}: {content}')
    prompt = rag_prompts.ASPECT_GROUP_PROMPT.format(movie=movie_name, product=movie_name, aspects=', '.join(ASPECTS), reviews='\n'.join(lines))
    try:
        raw = await complete_json(prompt, rag_prompts.ASPECT_GROUP_SYSTEM, max_tokens=max_tokens_for_task(TASK_ASPECT_GROUP), task=TASK_ASPECT_GROUP)
        parsed = _parse_json(raw)
        groups = None
        if isinstance(parsed, dict):
            groups = parsed.get('groups') or parsed.get('items')
        elif isinstance(parsed, list):
            groups = parsed
        if groups:
            valid = []
            for g in groups:
                if not isinstance(g, dict) or not g.get('aspect') or (not g.get('content')):
                    continue
                aspect = str(g['aspect']).lower().strip()
                if aspect not in ASPECTS:
                    aspect = 'other'
                valid.append({'aspect': aspect, 'review_ids': g.get('review_ids') or [], 'content': str(g['content'])[:8000], 'positive_percent': g.get('positive_percent'), 'negative_percent': g.get('negative_percent')})
            if valid:
                return valid
    except Exception as exc:
        logger.warning('[summarize] group_aspects LLM failed: %s', exc)
    return _fallback_group(curated)

async def _llm_summarize_aspect(aspect: str, chunk_content: str, *, movie_name: str) -> dict:
    """(Nội bộ) Llm summarize aspect (async).

    Args:
        aspect: (str) Tham số `aspect`.
        chunk_content: (str) Tham số `chunk_content`.
        movie_name: (str) Tham số `movie_name`.

    Returns:
        (dict) Kết quả trả về."""
    prompt = rag_prompts.ASPECT_SUMMARY_PROMPT.format(movie=movie_name, product=movie_name, aspect=aspect, content=chunk_content[:6000])
    try:
        raw = await complete_json(prompt, rag_prompts.ASPECT_SUMMARY_SYSTEM, max_tokens=max_tokens_for_task(TASK_ASPECT_SUMMARY), task=TASK_ASPECT_SUMMARY)
        parsed = _parse_json(raw)
        if isinstance(parsed, dict) and parsed.get('summary'):
            return {'summary': str(parsed['summary'])[:2000], 'pros': parsed.get('pros') or [], 'cons': parsed.get('cons') or [], 'positive_percent': parsed.get('positive_percent')}
    except Exception as exc:
        logger.warning('[summarize] summarize_aspect LLM failed aspect=%s: %s', aspect, exc)
    return {'summary': f'Tóm tắt {aspect} cho {movie_name}: {chunk_content[:300]}...', 'pros': [], 'cons': [], 'positive_percent': None}

async def handle_movie_summarize(envelope: dict) -> None:
    """Xử lý movie summarize (async)."""
    payload = envelope.get('payload') or {}
    movie_id = payload.get('movie_id') or envelope.get('video_id')
    if not movie_id:
        return
    movie_row = await get_movie(movie_id)
    movie_name = (movie_row or {}).get('name') or movie_id
    curated = await get_curated_reviews(movie_id, limit=getattr(settings, "AGENT_CURATED_TOP_N", 300))
    if not curated:
        logger.warning('[summarize] no curated movie=%s', movie_id)
        return
    groups = await _llm_group_aspects(curated, movie_name=movie_name)
    aspects = [g['aspect'] for g in groups]
    chunk_rows = []
    for g in groups:
        chunk_rows.append({'id': f"chk:{movie_id}:{g['aspect']}", 'movie_id': movie_id, 'aspect': g['aspect'], 'content': g['content'], 'review_ids': g.get('review_ids') or [], 'positive_percent': g.get('positive_percent'), 'negative_percent': g.get('negative_percent')})
    await delete_aspect_chunks_for_movie(movie_id, keep_aspects=aspects)
    vectors = await embed_texts([r['content'] for r in chunk_rows])
    for row, vec in zip(chunk_rows, vectors):
        row['embedding'] = vec
    await upsert_aspect_chunks(chunk_rows)
    for row in chunk_rows:
        aspect = row['aspect']
        meta = await _llm_summarize_aspect(aspect, row['content'], movie_name=movie_name)
        summary_vec = (await embed_texts([meta['summary']]))[0]
        await upsert_aspect_summary(id=f'sum:{movie_id}:{aspect}', movie_id=movie_id, aspect=aspect, summary=meta['summary'], pros=meta.get('pros') or [], cons=meta.get('cons') or [], positive_percent=meta.get('positive_percent'), source_chunk_ids=[row['id']], embedding=summary_vec)
    meta = dict((movie_row or {}).get('metadata') or {})
    meta['last_summarize_raw_count'] = await count_raw_reviews(movie_id)
    meta['summarized_at'] = envelope.get('fetched_at') or ''
    await upsert_movie(id=movie_id, name=movie_name, platform=(movie_row or {}).get('platform') or 'mixed', metadata=meta)
    logger.info('[summarize] done movie=%s chunks=%d aspects=%s', movie_id, len(chunk_rows), aspects)
