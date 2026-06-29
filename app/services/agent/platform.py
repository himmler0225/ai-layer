from __future__ import annotations
from typing import Dict, List
import app.config.settings as settings
from app.config.logger import Logger
from app.ingest.mappers.social_review import slugify_product_id
from app.rag.knowledge import is_product_fresh, product_has_knowledge
from app.rag.product_hint import PRODUCT_BLOCK_MARKER, current_question, extract_product_name
from app.services.agent.constants import _TIKTOK, _YOUTUBE
logger = Logger.get(__name__)
_PRODUCT_CORE = frozenset({'search_product_summary', 'search_aspect_evidence', 'get_raw_reviews', 'youtube_search', 'youtube_get_comments_batch', 'youtube_get_transcript_batch', 'youtube_get_detail', 'youtube_get_comments', 'extract_id_from_url'})
_RAG_CACHE_TOOLS = frozenset({'search_product_summary', 'search_aspect_evidence', 'get_raw_reviews', 'extract_id_from_url'})

def detect_platform(task: str) -> str | None:
    question = current_question(task)
    has_tiktok = bool(_TIKTOK.search(question))
    has_youtube = bool(_YOUTUBE.search(question))
    if has_tiktok and (not has_youtube):
        return 'tiktok'
    if has_youtube and (not has_tiktok):
        return 'youtube'
    return None

def filter_tools_by_platform(tools: List[Dict], task: str) -> List[Dict]:
    platform = detect_platform(task)
    if platform is None:
        return tools
    blocked = 'tiktok_' if platform == 'youtube' else 'youtube_'
    filtered = [t for t in tools if not t.get('name', '').startswith(blocked)]
    if len(filtered) != len(tools):
        logger.info('[agent] platform=%s blocked=%s* tools=%d/%d', platform, blocked, len(filtered), len(tools))
    return filtered

def _narrow_for_product_context(tools: List[Dict], task: str) -> List[Dict]:
    if PRODUCT_BLOCK_MARKER not in (task or ''):
        return tools
    if detect_platform(task):
        return tools
    narrowed = [t for t in tools if t.get('name') in _PRODUCT_CORE]
    if narrowed and len(narrowed) < len(tools):
        logger.info('[agent] product context: tools %d → %d', len(tools), len(narrowed))
        return narrowed
    return tools

async def _narrow_for_rag_cache(tools: List[Dict], task: str) -> List[Dict]:
    if not settings.RAG_ENABLED:
        return tools
    product_name = extract_product_name(task)
    if not product_name:
        return tools
    product_id = slugify_product_id(product_name)
    if not await product_has_knowledge(product_id):
        return tools
    if not await is_product_fresh(product_id):
        return tools
    rag_tools = [t for t in tools if t.get('name') in _RAG_CACHE_TOOLS]
    if rag_tools and len(rag_tools) < len(tools):
        logger.info('[agent] RAG cache hit product=%s tools=%d → %d', product_id, len(tools), len(rag_tools))
        return rag_tools
    return tools

async def prepare_tools_for_task(tools: List[Dict], task: str) -> List[Dict]:
    tools = filter_tools_by_platform(tools, task)
    tools = _narrow_for_product_context(tools, task)
    tools = await _narrow_for_rag_cache(tools, task)
    return tools

def prepare_tools(tools: List[Dict], task: str) -> List[Dict]:
    tools = filter_tools_by_platform(tools, task)
    return _narrow_for_product_context(tools, task)
