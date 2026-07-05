"""MCP crawl tool catalog — list_tools from data-miner → OpenAI function schemas."""

import time
from typing import Any

from app.config.logger import Logger
from app.mcp.client import list_tools as mcp_list_tools

logger = Logger.get(__name__)

CATALOG_TTL_SEC = 300

_PLATFORM_PREFIX = {
    "youtube": "youtube_",
    "tiktok": "tiktok_",
    "movies": "movie_",
}


def mcp_tool_to_openai(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "name": tool["name"],
        "description": tool.get("description") or "",
        "parameters": tool.get("inputSchema") or {"type": "object", "properties": {}},
    }


class CrawlToolCatalog:
    def __init__(self) -> None:
        self._tools: list[dict[str, Any]] = []
        self._schemas: dict[str, dict[str, Any]] = {}
        self._names: frozenset[str] = frozenset()
        self._loaded_at: float = 0.0

    async def refresh(self) -> list[dict[str, Any]]:
        raw = await mcp_list_tools()
        self._tools = [mcp_tool_to_openai(t) for t in raw]
        self._schemas = {t["name"]: t["parameters"] for t in self._tools}
        self._names = frozenset(self._schemas)
        self._loaded_at = time.monotonic()
        logger.info("[mcp] catalog loaded tools=%d", len(self._tools))
        return self._tools

    async def get_openai_tools(self, *, force_refresh: bool = False) -> list[dict[str, Any]]:
        stale = (time.monotonic() - self._loaded_at) > CATALOG_TTL_SEC
        if force_refresh or not self._tools or stale:
            await self.refresh()
        return list(self._tools)

    async def get_tool_names(self) -> frozenset[str]:
        if not self._tools:
            await self.get_openai_tools()
        return self._names

    async def get_schema(self, name: str) -> dict[str, Any] | None:
        if not self._schemas:
            await self.get_openai_tools()
        return self._schemas.get(name)

    def filter_by_platform(self, tools: list[dict[str, Any]], platform: str) -> list[dict[str, Any]]:
        prefix = _PLATFORM_PREFIX.get(platform)
        if not prefix:
            return tools
        return [t for t in tools if t.get("name", "").startswith(prefix)]


crawl_catalog = CrawlToolCatalog()
