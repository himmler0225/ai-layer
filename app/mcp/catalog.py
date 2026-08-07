"""MCP crawl tool catalog — list_tools from data-miner → OpenAI function schemas."""

import time
from typing import Any

from app.config.logger import Logger, log_event
from app.mcp.client import list_tools as mcp_list_tools

logger = Logger.get(__name__)

CATALOG_TTL_SEC = 300

_PLATFORM_PREFIX = {
    "youtube": "youtube_",
    "tiktok": "tiktok_",
    "movies": "movie_",
}


def mcp_tool_to_openai(tool: dict[str, Any]) -> dict[str, Any]:
    """Convert an MCP tool definition into an OpenAI function-tool schema.

    Args:
        tool: An MCP tool dict with `name`, optional `description`, and
            `inputSchema`.

    Returns:
        An OpenAI `{"type": "function", "name", "description", "parameters"}`
        tool spec, defaulting to an empty object schema if `inputSchema` is
        missing."""
    return {
        "type": "function",
        "name": tool["name"],
        "description": tool.get("description") or "",
        "parameters": tool.get("inputSchema") or {"type": "object", "properties": {}},
    }


class CrawlToolCatalog:
    def __init__(self) -> None:
        """Initialize an empty catalog with no tools loaded yet.

        Returns:
            None."""
        self._tools: list[dict[str, Any]] = []
        self._schemas: dict[str, dict[str, Any]] = {}
        self._names: frozenset[str] = frozenset()
        self._loaded_at: float = 0.0

    async def refresh(self) -> list[dict[str, Any]]:
        """Reload the tool catalog from MCP `list_tools`, replacing cached state.

        Returns:
            The refreshed list of OpenAI-format tool specs."""
        raw = await mcp_list_tools()
        self._tools = [mcp_tool_to_openai(t) for t in raw]
        self._schemas = {t["name"]: t["parameters"] for t in self._tools}
        self._names = frozenset(self._schemas)
        self._loaded_at = time.monotonic()
        logger.info(log_event("mcp", "catalog loaded", tools=len(self._tools)))
        return self._tools

    async def get_openai_tools(self, *, force_refresh: bool = False) -> list[dict[str, Any]]:
        """Get the cached OpenAI-format tool list, refreshing it if stale or empty.

        Args:
            force_refresh: If `True`, always reload from MCP regardless of
                cache age.

        Returns:
            The list of OpenAI-format tool specs."""
        stale = (time.monotonic() - self._loaded_at) > CATALOG_TTL_SEC
        if force_refresh or not self._tools or stale:
            await self.refresh()
        return list(self._tools)

    async def get_tool_names(self) -> frozenset[str]:
        """Get the set of known tool names, loading the catalog first if empty.

        Returns:
            A frozenset of all catalog tool names."""
        if not self._tools:
            await self.get_openai_tools()
        return self._names

    async def get_schema(self, name: str) -> dict[str, Any] | None:
        """Get the input-parameters schema for a single tool by name.

        Args:
            name: The tool name to look up.

        Returns:
            The tool's parameters schema dict, or `None` if not found."""
        if not self._schemas:
            await self.get_openai_tools()
        return self._schemas.get(name)

    def filter_by_platform(self, tools: list[dict[str, Any]], platform: str) -> list[dict[str, Any]]:
        """Filter tools to those belonging to a given crawl platform.

        Args:
            tools: Tool specs to filter, as OpenAI-format dicts with a `name`.
            platform: One of the known platform keys (`"youtube"`, `"tiktok"`,
                `"movies"`); unrecognized platforms return `tools` unchanged.

        Returns:
            The tools whose name starts with the platform's prefix."""
        prefix = _PLATFORM_PREFIX.get(platform)
        if not prefix:
            return tools
        return [t for t in tools if t.get("name", "").startswith(prefix)]


crawl_catalog = CrawlToolCatalog()
