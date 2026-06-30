from __future__ import annotations
import re
from typing import Dict, List
import app.config.settings as settings
from app.config.logger import Logger
from app.ingest.mappers.social_review import slugify_movie_id
from app.rag.knowledge import is_movie_fresh, movie_has_knowledge
from app.rag.movie_hint import MOVIE_BLOCK_MARKER, current_question, extract_movie_name, has_movie_context
from app.services.agent.constants import _TIKTOK, _YOUTUBE
logger = Logger.get(__name__)
_MOVIE_CORE = frozenset({'search_movie_summary', 'search_aspect_evidence', 'get_raw_reviews', 'youtube_search', 'youtube_get_comments_batch', 'youtube_get_transcript_batch', 'youtube_get_detail', 'youtube_get_comments', 'extract_id_from_url'})
_RAG_CACHE_TOOLS = frozenset({'search_movie_summary', 'search_aspect_evidence', 'get_raw_reviews', 'extract_id_from_url'})
_REVIEW_QUERY = re.compile(
    r'\b(review|users?\s+say|đánh\s+giá|người\s+dùng|nên\s+xem|worth\s+watching)\b',
    re.IGNORECASE,
)

def detect_platform(task: str) -> str | None:
    """Phát hiện platform.

    Args:
        task: (str) Tham số `task`.

    Returns:
        (str | None) Kết quả trả về."""
    question = current_question(task)
    has_tiktok = bool(_TIKTOK.search(question))
    has_youtube = bool(_YOUTUBE.search(question))
    if has_tiktok and (not has_youtube):
        return 'tiktok'
    if has_youtube and (not has_tiktok):
        return 'youtube'
    return None


def filter_tools_by_platform(tools: List[Dict], task: str) -> List[Dict]:
    """Lọc tools by platform.

    Args:
        tools: (List[Dict]) Tham số `tools`.
        task: (str) Tham số `task`.

    Returns:
        (List[Dict]) Kết quả trả về."""
    platform = detect_platform(task)
    if platform is None:
        return tools
    blocked = 'tiktok_' if platform == 'youtube' else 'youtube_'
    filtered = [t for t in tools if not t.get('name', '').startswith(blocked)]
    if len(filtered) != len(tools):
        logger.info('[agent] platform=%s blocked=%s* tools=%d/%d', platform, blocked, len(filtered), len(tools))
    return filtered

def _narrow_for_movie_context(tools: List[Dict], task: str) -> List[Dict]:
    """Thu hẹp tool khi task có ngữ cảnh phim."""
    if not has_movie_context(task):
        return tools
    if detect_platform(task):
        return tools
    narrowed = [t for t in tools if t.get('name') in _MOVIE_CORE]
    if narrowed and len(narrowed) < len(tools):
        logger.info('[agent] movie context: tools %d → %d', len(tools), len(narrowed))
        return narrowed
    return tools

def _narrow_for_review_query(tools: List[Dict], task: str) -> List[Dict]:
    """Thu hẹp tool khi câu hỏi dạng review phim (không có block phim)."""
    if has_movie_context(task):
        return tools
    question = current_question(task)
    if not _REVIEW_QUERY.search(question):
        return tools
    narrowed = [t for t in tools if t.get('name') in _MOVIE_CORE]
    if narrowed and len(narrowed) < len(tools):
        logger.info('[agent] review query: tools %d → %d', len(tools), len(narrowed))
        return narrowed
    return tools

async def _narrow_for_rag_cache(tools: List[Dict], task: str) -> List[Dict]:
    """(Nội bộ) Narrow for rag cache (async).

    Args:
        tools: (List[Dict]) Tham số `tools`.
        task: (str) Tham số `task`.

    Returns:
        (List[Dict]) Kết quả trả về."""
    if not settings.RAG_ENABLED:
        return tools
    movie_name = extract_movie_name(task)
    if not movie_name:
        return tools
    movie_id = slugify_movie_id(movie_name)
    if not await movie_has_knowledge(movie_id):
        return tools
    if not await is_movie_fresh(movie_id):
        return tools
    rag_tools = [t for t in tools if t.get('name') in _RAG_CACHE_TOOLS]
    if rag_tools and len(rag_tools) < len(tools):
        logger.info('[agent] RAG cache hit movie=%s tools=%d → %d', movie_id, len(tools), len(rag_tools))
        return rag_tools
    return tools

async def prepare_tools_for_task(tools: List[Dict], task: str) -> List[Dict]:
    """Chuẩn bị tools for task (async).

    Args:
        tools: (List[Dict]) Tham số `tools`.
        task: (str) Tham số `task`.

    Returns:
        (List[Dict]) Kết quả trả về."""
    tools = filter_tools_by_platform(tools, task)
    tools = _narrow_for_review_query(tools, task)
    tools = _narrow_for_movie_context(tools, task)
    tools = await _narrow_for_rag_cache(tools, task)
    return tools

def prepare_tools(tools: List[Dict], task: str) -> List[Dict]:
    """Chuẩn bị tools.

    Args:
        tools: (List[Dict]) Tham số `tools`.
        task: (str) Tham số `task`.

    Returns:
        (List[Dict]) Kết quả trả về."""
    tools = filter_tools_by_platform(tools, task)
    return _narrow_for_movie_context(tools, task)
