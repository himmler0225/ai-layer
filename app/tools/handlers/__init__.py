from app.tools.handlers.crawl import CRAWL_HANDLERS
from app.tools.handlers.rag import RAG_HANDLERS

TOOL_HANDLERS = {**CRAWL_HANDLERS, **RAG_HANDLERS}
