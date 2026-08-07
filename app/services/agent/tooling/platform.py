import re
from app.rag.config import RAG_ENABLED
from app.config.logger import Logger, log_event
from app.ingest.mappers.social_review import slugify_movie_id
from app.rag.knowledge import is_movie_fresh, movie_has_knowledge
from app.rag.movie_hint import (
    context_for_filtering,
    current_question,
    extract_movie_name,
    has_movie_context,
    wants_catalog,
    wants_raw_comments,
    wants_review,
)
from app.services.agent.domains import DOMAINS

logger = Logger.get(__name__)
# Domains with a mention_re (detected by name being mentioned in the question)
# — currently youtube/tiktok. "movies" has no mention_re so it does not
# participate in this detect/block-by-platform-name mechanism (it's selected
# via wants_catalog() instead, a different mechanism, not "platform named").
_MENTIONABLE_DOMAINS = [(d["id"], d["mention_re"]) for d in DOMAINS if d.get("mention_re")]
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
        # TikTok — previously missing here, which caused review-query narrowing
        # to strip all tiktok_* tools from any tool list that was TikTok-only
        # (e.g. the multi-agent tiktok worker), leaving only extract_id_from_url.
        "tiktok_search",
        "tiktok_comments",
        "tiktok_transcript",
        "tiktok_video_info",
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

_ECOSYSTEM_PREFIXES = ("youtube_", "tiktok_", "movie_")


def _is_movie_ecosystem(tools: list[dict]) -> bool:
    """(Internal) Check whether a tool list belongs to the youtube/tiktok/movies ecosystem."""
    return any(t.get("name", "").startswith(_ECOSYSTEM_PREFIXES) for t in tools)


def _is_catalog_tool(name: str) -> bool:
    """(Internal) Check whether a tool name belongs to the movie catalog toolset.

    Args:
        name: (str) Tool name to check.

    Returns:
        (bool) True if `name` starts with "movie_" or is "extract_id_from_url"."""
    return name.startswith("movie_") or name == "extract_id_from_url"


def detect_platform(task: str) -> str | None:
    """Detect a single social platform (youtube/tiktok) explicitly named in the task.

    Args:
        task: (str) The user task/question to scan.

    Returns:
        (str | None) The domain id if exactly one mentionable platform is
        named in the task; None if zero or more than one are mentioned."""
    question = context_for_filtering(task)
    mentioned = [domain_id for domain_id, pattern in _MENTIONABLE_DOMAINS if pattern.search(question)]
    if len(mentioned) == 1:
        return mentioned[0]
    return None


def filter_tools_by_platform(tools: list[dict], task: str) -> list[dict]:
    """Drop tools belonging to other mentionable platforms when exactly one platform is named in the task.

    Args:
        tools: (list[dict]) Tool definitions to filter.
        task: (str) The user task/question, used to detect the mentioned platform.

    Returns:
        (list[dict]) `tools` unchanged if no single platform is detected;
        otherwise `tools` with any tool whose name is prefixed by a
        non-mentioned platform's domain id removed."""
    platform = detect_platform(task)
    if platform is None:
        return tools
    blocked = tuple(f"{domain_id}_" for domain_id, _ in _MENTIONABLE_DOMAINS if domain_id != platform)
    filtered = [t for t in tools if not t.get("name", "").startswith(blocked)]
    if len(filtered) != len(tools):
        logger.info(
            log_event(
                "agent",
                "platform filter applied",
                platform=platform,
                blocked=blocked,
                kept=len(filtered),
                total=len(tools),
            )
        )
    return filtered


def _narrow_for_raw_comments(tools: list[dict], task: str) -> list[dict] | None:
    """(Internal) Narrow tools to just comment-related ones when the task asks for raw comments.

    Args:
        tools: (list[dict]) Tool definitions to narrow.
        task: (str) The user task/question.

    Returns:
        (list[dict] | None) The subset of `tools` found in _COMMENT_TOOLS if
        the task wants raw comments and narrowing actually reduces the list;
        None otherwise (caller should keep the original tools)."""
    ctx = context_for_filtering(task)
    if not wants_raw_comments(ctx) and not wants_raw_comments(current_question(task)):
        return None
    narrowed = [t for t in tools if t.get("name") in _COMMENT_TOOLS]
    if narrowed and len(narrowed) < len(tools):
        logger.info(
            log_event("agent", "tool filter applied", intent="raw_comments", before=len(tools), after=len(narrowed))
        )
        return narrowed
    return None


def _narrow_for_catalog_query(tools: list[dict], task: str) -> list[dict] | None:
    """(Internal) Narrow tools to just catalog tools for pure catalog queries (no review intent).

    Args:
        tools: (list[dict]) Tool definitions to narrow.
        task: (str) The user task/question.

    Returns:
        (list[dict] | None) The subset of `tools` that are catalog tools, if
        the task wants catalog info and has no review intent; None if the
        task isn't a catalog query, mixes in review intent, or no catalog
        tools were found."""
    ctx = context_for_filtering(task)
    question = current_question(task)
    if not wants_catalog(ctx) and not wants_catalog(question):
        return None
    if wants_review(ctx) or wants_review(question):
        return None
    narrowed = [t for t in tools if _is_catalog_tool(t.get("name", ""))]
    if narrowed and len(narrowed) < len(tools):
        logger.info(
            log_event("agent", "tool filter applied", intent="catalog", before=len(tools), after=len(narrowed))
        )
        return narrowed
    return narrowed if narrowed else None


def _narrow_for_movie_context(tools: list[dict], task: str) -> list[dict]:
    """(Internal) Narrow tools to the core movie/review toolset when the task has movie context and no single platform is named.

    Args:
        tools: (list[dict]) Tool definitions to narrow.
        task: (str) The user task/question.

    Returns:
        (list[dict]) `tools` unchanged if there's no movie context, a single
        platform was explicitly detected, or narrowing would not reduce the
        list; otherwise the subset of `tools` found in _MOVIE_CORE."""
    if not has_movie_context(task):
        return tools
    if detect_platform(task):
        return tools
    narrowed = [t for t in tools if t.get("name") in _MOVIE_CORE]
    if narrowed and len(narrowed) < len(tools):
        logger.info(
            log_event("agent", "tool filter applied", intent="movie_context", before=len(tools), after=len(narrowed))
        )
        return narrowed
    return tools


def _narrow_for_review_query(tools: list[dict], task: str) -> list[dict]:
    """(Internal) Narrow tools to the core movie/review toolset when the task looks like a review query.

    Args:
        tools: (list[dict]) Tool definitions to narrow.
        task: (str) The user task/question.

    Returns:
        (list[dict]) `tools` unchanged if there's already movie context, the
        task doesn't express review intent, or narrowing would not reduce
        the list; otherwise the subset of `tools` found in _MOVIE_CORE."""
    if has_movie_context(task):
        return tools
    ctx = context_for_filtering(task)
    if not wants_review(ctx) and not _REVIEW_QUERY.search(current_question(task)):
        return tools
    narrowed = [t for t in tools if t.get("name") in _MOVIE_CORE]
    if narrowed and len(narrowed) < len(tools):
        logger.info(
            log_event("agent", "tool filter applied", intent="review_query", before=len(tools), after=len(narrowed))
        )
        return narrowed
    return tools


async def _narrow_for_rag_cache(tools: list[dict], task: str) -> list[dict]:
    """(Internal) Narrow tools to RAG-backed lookups when a fresh knowledge cache exists for the mentioned movie (async).

    Args:
        tools: (list[dict]) Tool definitions to narrow.
        task: (str) The user task/question, used to extract a movie name.

    Returns:
        (list[dict]) `tools` unchanged if RAG is disabled, no movie name is
        found, the movie has no cached knowledge, the cache is stale, or
        narrowing would not reduce the list; otherwise the subset of `tools`
        found in _RAG_CACHE_TOOLS."""
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
        logger.info(
            log_event(
                "agent",
                "rag cache hit",
                movie_id=movie_id,
                before=len(tools),
                after=len(rag_tools),
            )
        )
        return rag_tools
    return tools


async def prepare_tools_for_task(tools: list[dict], task: str) -> list[dict]:
    """Run the full tool-narrowing pipeline for a task, including the async RAG cache check (async).

    Applies platform filtering, then (for movie-ecosystem tool lists) narrows
    by raw-comments intent, catalog intent, review intent, movie context, and
    finally RAG cache freshness, in that order — the first narrowing that
    applies for raw-comments/catalog short-circuits the rest.

    Args:
        tools: (list[dict]) Tool definitions available for the task.
        task: (str) The user task/question driving the narrowing decisions.

    Returns:
        (list[dict]) The narrowed tool list to actually offer the LLM."""
    tools = filter_tools_by_platform(tools, task)
    if not _is_movie_ecosystem(tools):
        return tools
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
    """Run the synchronous tool-narrowing pipeline for a task (no RAG cache check).

    Same as `prepare_tools_for_task` but skips the async RAG-cache narrowing
    step and does not apply review-query narrowing before the movie-context
    narrowing.

    Args:
        tools: (list[dict]) Tool definitions available for the task.
        task: (str) The user task/question driving the narrowing decisions.

    Returns:
        (list[dict]) The narrowed tool list to actually offer the LLM."""
    tools = filter_tools_by_platform(tools, task)
    if not _is_movie_ecosystem(tools):
        return tools
    comments = _narrow_for_raw_comments(tools, task)
    if comments is not None:
        return comments
    catalog = _narrow_for_catalog_query(tools, task)
    if catalog is not None:
        return catalog
    return _narrow_for_movie_context(tools, task)
