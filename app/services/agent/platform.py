import re
from app.rag.config import RAG_ENABLED
from app.config.logger import Logger
from app.ingest.mappers.social_review import slugify_movie_id
from app.rag.knowledge import is_movie_fresh, movie_has_knowledge
from app.rag.movie_hint import (
    context_for_filtering,
    current_question,
    extract_movie_name,
    has_movie_context,
    is_short_followup,
    wants_catalog,
    wants_raw_comments,
    wants_review,
)
from app.services.agent.constants import _TIKTOK, _YOUTUBE

logger = Logger.get(__name__)
_MOVIE_CORE = frozenset(
    {
        "search_movie_summary",
        "search_aspect_evidence",
        "get_raw_reviews",
        "youtube_search",
        "youtube_get_comments_batch",
        "youtube_get_transcript_batch",
        "youtube_get_detail",
        "youtube_get_comments",
        "extract_id_from_url",
    }
)
_COMMENT_TOOLS = frozenset(
    {
        "extract_id_from_url",
        "youtube_get_comments",
        "youtube_get_comments_batch",
        "tiktok_comments",
        "tiktok_video_info",
    }
)
_RAG_CACHE_TOOLS = frozenset(
    {"search_movie_summary", "search_aspect_evidence", "get_raw_reviews", "extract_id_from_url"}
)
_REVIEW_QUERY = re.compile(
    r"\b(review|users?\s+say|đánh\s+giá|người\s+dùng|nên\s+xem|worth\s+watching)\b",
    re.IGNORECASE,
)


def _is_catalog_tool(name: str) -> bool:
    return name.startswith("movie_") or name == "extract_id_from_url"


def detect_platform(task: str) -> str | None:
    question = context_for_filtering(task)
    has_tiktok = bool(_TIKTOK.search(question))
    has_youtube = bool(_YOUTUBE.search(question))
    if has_tiktok and (not has_youtube):
        return "tiktok"
    if has_youtube and (not has_tiktok):
        return "youtube"
    return None


def filter_tools_by_platform(tools: list[dict], task: str) -> list[dict]:
    platform = detect_platform(task)
    if platform is None:
        return tools
    blocked = "tiktok_" if platform == "youtube" else "youtube_"
    filtered = [t for t in tools if not t.get("name", "").startswith(blocked)]
    if len(filtered) != len(tools):
        logger.info("[agent] platform=%s blocked=%s* tools=%d/%d", platform, blocked, len(filtered), len(tools))
    return filtered


def _narrow_for_raw_comments(tools: list[dict], task: str) -> list[dict] | None:
    ctx = context_for_filtering(task)
    if not wants_raw_comments(ctx) and not wants_raw_comments(current_question(task)):
        return None
    narrowed = [t for t in tools if t.get("name") in _COMMENT_TOOLS]
    if narrowed and len(narrowed) < len(tools):
        logger.info("[agent] raw comments intent: tools %d → %d", len(tools), len(narrowed))
        return narrowed
    return None


def _narrow_for_catalog_query(tools: list[dict], task: str) -> list[dict] | None:
    ctx = context_for_filtering(task)
    question = current_question(task)
    if not wants_catalog(ctx) and not wants_catalog(question):
        return None
    if wants_review(ctx) or wants_review(question):
        return None
    narrowed = [t for t in tools if _is_catalog_tool(t.get("name", ""))]
    if narrowed and len(narrowed) < len(tools):
        logger.info("[agent] catalog intent: tools %d → %d", len(tools), len(narrowed))
        return narrowed
    return narrowed if narrowed else None


def _narrow_for_movie_context(tools: list[dict], task: str) -> list[dict]:
    if not has_movie_context(task):
        return tools
    if detect_platform(task):
        return tools
    narrowed = [t for t in tools if t.get("name") in _MOVIE_CORE]
    if narrowed and len(narrowed) < len(tools):
        logger.info("[agent] movie context: tools %d → %d", len(tools), len(narrowed))
        return narrowed
    return tools


def _narrow_for_review_query(tools: list[dict], task: str) -> list[dict]:
    if has_movie_context(task):
        return tools
    ctx = context_for_filtering(task)
    if not wants_review(ctx) and not _REVIEW_QUERY.search(current_question(task)):
        return tools
    narrowed = [t for t in tools if t.get("name") in _MOVIE_CORE]
    if narrowed and len(narrowed) < len(tools):
        logger.info("[agent] review query: tools %d → %d", len(tools), len(narrowed))
        return narrowed
    return tools


async def _narrow_for_rag_cache(tools: list[dict], task: str) -> list[dict]:
    if not RAG_ENABLED:
        return tools
    movie_name = extract_movie_name(task)
    if not movie_name:
        return tools
    movie_id = slugify_movie_id(movie_name)
    if not await movie_has_knowledge(movie_id):
        return tools
    if not await is_movie_fresh(movie_id):
        return tools
    rag_tools = [t for t in tools if t.get("name") in _RAG_CACHE_TOOLS]
    if rag_tools and len(rag_tools) < len(tools):
        logger.info("[agent] RAG cache hit movie=%s tools=%d → %d", movie_id, len(tools), len(rag_tools))
        return rag_tools
    return tools


async def prepare_tools_for_task(tools: list[dict], task: str) -> list[dict]:
    tools = filter_tools_by_platform(tools, task)
    comments = _narrow_for_raw_comments(tools, task)
    if comments is not None:
        return comments
    catalog = _narrow_for_catalog_query(tools, task)
    if catalog is not None:
        return catalog
    tools = _narrow_for_review_query(tools, task)
    tools = _narrow_for_movie_context(tools, task)
    tools = await _narrow_for_rag_cache(tools, task)
    return tools


def prepare_tools(tools: list[dict], task: str) -> list[dict]:
    tools = filter_tools_by_platform(tools, task)
    comments = _narrow_for_raw_comments(tools, task)
    if comments is not None:
        return comments
    catalog = _narrow_for_catalog_query(tools, task)
    if catalog is not None:
        return catalog
    return _narrow_for_movie_context(tools, task)
