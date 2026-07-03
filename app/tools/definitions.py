from app.rag.config import RAG_ENABLED
from app.tools.movie_definitions import MOVIE_TOOLS
from app.tools.rag_definitions import RAG_TOOLS
from app.tools.tiktok_definitions import TIKTOK_TOOLS
from app.tools.util_definitions import UTIL_TOOLS
from app.tools.youtube_definitions import YOUTUBE_TOOLS

_RAG = RAG_TOOLS if RAG_ENABLED else []

ALL_TOOLS = _RAG + YOUTUBE_TOOLS + TIKTOK_TOOLS + MOVIE_TOOLS + UTIL_TOOLS
TOOL_SETS = {
    "youtube": _RAG + YOUTUBE_TOOLS + UTIL_TOOLS,
    "tiktok": _RAG + TIKTOK_TOOLS + UTIL_TOOLS,
    "movies": MOVIE_TOOLS + UTIL_TOOLS,
    "all": ALL_TOOLS,
}
