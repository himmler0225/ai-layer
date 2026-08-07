import json
from typing import Any

import jsonschema

from app.mcp.config import AGENT_CRAWL_BACKEND
from app.rag.config import RAG_ENABLED
from app.tools.handlers import TOOL_HANDLERS
from app.tools.handlers.rag import is_rag_enabled, rag_disabled_error
from app.tools.movie_definitions import MOVIE_TOOLS
from app.tools.rag_definitions import RAG_TOOLS
from app.tools.tiktok_definitions import TIKTOK_TOOLS
from app.tools.util_definitions import UTIL_TOOLS
from app.tools.web_definitions import WEB_TOOLS
from app.tools.youtube_definitions import YOUTUBE_TOOLS

_RAG_TOOL_NAMES = frozenset(t["name"] for t in RAG_TOOLS)
_UTIL_TOOL_NAMES = frozenset(t["name"] for t in UTIL_TOOLS)
_LEGACY_CRAWL_NAMES = frozenset(
    t["name"] for t in (*YOUTUBE_TOOLS, *TIKTOK_TOOLS, *MOVIE_TOOLS, *WEB_TOOLS)
)

_STATIC_SCHEMAS: dict[str, dict] = {
    tool["name"]: tool["parameters"]
    for tool in (*(RAG_TOOLS if RAG_ENABLED else []), *YOUTUBE_TOOLS, *TIKTOK_TOOLS, *MOVIE_TOOLS, *WEB_TOOLS, *UTIL_TOOLS)
}


async def _schema_for(name: str) -> dict | None:
    """Look up the JSON schema used to validate a tool's input parameters.

    Prefers the MCP crawl catalog's schema (when the MCP backend is
    active) and falls back to the static tool-definition schemas.

    Args:
        name: Tool name to look up.

    Returns:
        The tool's parameter JSON schema, or None if the tool is unknown.
    """
    if AGENT_CRAWL_BACKEND == "mcp":
        from app.mcp.catalog import crawl_catalog

        schema = await crawl_catalog.get_schema(name)
        if schema is not None:
            return schema
    return _STATIC_SCHEMAS.get(name)


async def _is_crawl_tool(name: str) -> bool:
    """Determine whether a tool name belongs to the crawl (data-miner) toolset.

    Args:
        name: Tool name to check.

    Returns:
        False for util tools; otherwise True if the name is registered in
        the MCP crawl catalog (when MCP backend is active) or in the
        legacy static crawl tool sets.
    """
    if name in _UTIL_TOOL_NAMES:
        return False
    if AGENT_CRAWL_BACKEND == "mcp":
        from app.mcp.catalog import crawl_catalog

        return name in await crawl_catalog.get_tool_names()
    return name in _LEGACY_CRAWL_NAMES


def _unwrap_data_miner_result(result: Any, name: str) -> dict:
    """Unwrap a data-miner-style {"success": ..., "data": ...} envelope into a plain dict.

    Args:
        result: Raw result returned by a tool handler.
        name: Tool name, used to annotate error results.

    Returns:
        The inner "data" payload on success; an {"error", "tool"} dict on
        failure; or the result as-is (wrapped in {"data": ...} if not
        already a dict) when it doesn't match the envelope shape.
    """
    if isinstance(result, dict):
        if result.get("success") is True and isinstance(result.get("data"), (dict, list)):
            return result["data"]
        if result.get("success") is False:
            return {"error": result.get("error") or "data-miner request failed", "tool": name}
    return result if isinstance(result, dict) else {"data": result}


async def _execute_http_tool(name: str, inputs: dict) -> dict:
    """Run a legacy (non-MCP) tool handler over HTTP and normalize its result.

    Args:
        name: Tool name to look up in `TOOL_HANDLERS`.
        inputs: Validated input arguments for the tool.

    Returns:
        The unwrapped tool result, or an {"error", "tool"} dict if the
        tool is unknown or raises an exception.
    """
    fn = TOOL_HANDLERS.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return _unwrap_data_miner_result(await fn(inputs), name)
    except Exception as exc:
        return {"error": str(exc), "tool": name}


async def _execute_mcp_tool(name: str, inputs: dict) -> dict:
    """Run a tool via the MCP crawl catalog client and normalize its result.

    Args:
        name: Tool name to call over MCP.
        inputs: Validated input arguments for the tool.

    Returns:
        The "data" payload on success (wrapped in {"data": ...} if not a
        dict), or an {"error", "tool"} dict on failure/exception.
    """
    from app.mcp.client import call_tool

    try:
        body = await call_tool(name, inputs)
    except Exception as exc:
        return {"error": str(exc), "tool": name}

    if body.get("success") is True:
        data = body.get("data")
        return data if isinstance(data, dict) else {"data": data}
    return {"error": body.get("error") or "tool failed", "tool": name}


async def execute_tool(name: str, inputs: dict, **kwargs) -> dict:
    """Validate inputs against the tool's schema and dispatch it to the right backend.

    Validates `inputs` against the tool's JSON schema (if found), then
    routes to the RAG handler, the util handler, the MCP crawl backend, or
    the legacy HTTP handler, depending on which set `name` belongs to and
    the configured `AGENT_CRAWL_BACKEND`.

    Args:
        name: Tool name to execute.
        inputs: Raw input arguments supplied by the LLM.
        **kwargs: Unused; accepted for call-signature compatibility.

    Returns:
        The tool's result dict, or an {"error": ...} dict on validation
        failure, RAG being disabled, or execution failure.
    """
    schema = await _schema_for(name)
    if schema:
        try:
            jsonschema.validate(instance=inputs, schema=schema)
        except jsonschema.ValidationError as exc:
            return {"error": f"Invalid input for {name}: {exc.message}"}

    if name in _RAG_TOOL_NAMES:
        if not is_rag_enabled():
            return rag_disabled_error()
        return _unwrap_data_miner_result(await TOOL_HANDLERS[name](inputs), name)

    if name in _UTIL_TOOL_NAMES:
        fn = TOOL_HANDLERS.get(name)
        if fn is None:
            return {"error": f"Unknown tool: {name}"}
        try:
            return _unwrap_data_miner_result(await fn(inputs), name)
        except Exception as exc:
            return {"error": str(exc), "tool": name}

    if AGENT_CRAWL_BACKEND == "mcp" and await _is_crawl_tool(name):
        return await _execute_mcp_tool(name, inputs)

    return await _execute_http_tool(name, inputs)
