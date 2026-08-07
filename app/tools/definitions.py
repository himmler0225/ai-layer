from app.rag.config import RAG_ENABLED
from app.tools.movie_definitions import MOVIE_TOOLS
from app.tools.rag_definitions import RAG_TOOLS
from app.tools.tiktok_definitions import TIKTOK_TOOLS
from app.tools.util_definitions import UTIL_TOOLS
from app.tools.web_definitions import WEB_TOOLS
from app.tools.youtube_definitions import YOUTUBE_TOOLS

_RAG = RAG_TOOLS if RAG_ENABLED else []

# Legacy static sets (AGENT_CRAWL_BACKEND=http)
ALL_TOOLS = _RAG + YOUTUBE_TOOLS + TIKTOK_TOOLS + MOVIE_TOOLS + WEB_TOOLS + UTIL_TOOLS
TOOL_SETS = {
    "youtube": _RAG + YOUTUBE_TOOLS + UTIL_TOOLS,
    "tiktok": _RAG + TIKTOK_TOOLS + UTIL_TOOLS,
    "movies": MOVIE_TOOLS + UTIL_TOOLS,
    "web": WEB_TOOLS + UTIL_TOOLS,
    "all": ALL_TOOLS,
}

_SET_PLATFORM = {
    "youtube": "youtube",
    "tiktok": "tiktok",
    "movies": "movies",
}


async def resolve_tool_set(name: str) -> list[dict]:
    """Return OpenAI tool schemas for a tool set (MCP catalog or static definitions)."""
    from app.mcp.config import AGENT_CRAWL_BACKEND

    key = name if name in TOOL_SETS else "all"
    # "web" does not go through the data-miner MCP crawl catalog (that catalog
    # covers youtube/tiktok/movies) — web_search is always a static tool that
    # calls the REST endpoint directly.
    if key == "web" or AGENT_CRAWL_BACKEND != "mcp":
        return TOOL_SETS[key]

    from app.mcp.catalog import crawl_catalog

    crawl = await crawl_catalog.get_openai_tools()
    platform = _SET_PLATFORM.get(key)
    if platform:
        crawl = crawl_catalog.filter_by_platform(crawl, platform)

    if key == "movies":
        return list(crawl) + UTIL_TOOLS
    return _RAG + list(crawl) + UTIL_TOOLS
