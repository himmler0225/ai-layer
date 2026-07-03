import json
from typing import Any

import jsonschema

from app.mcp.config import AGENT_CRAWL_BACKEND
from app.rag.config import RAG_ENABLED
from app.tools.definitions import TIKTOK_TOOLS, UTIL_TOOLS, YOUTUBE_TOOLS
from app.tools.handlers import TOOL_HANDLERS
from app.tools.handlers.rag import is_rag_enabled, rag_disabled_error
from app.tools.movie_definitions import MOVIE_TOOLS
from app.tools.rag_definitions import RAG_TOOLS

_RAG_TOOL_NAMES = frozenset(t["name"] for t in RAG_TOOLS)
_CRAWL_TOOL_NAMES = frozenset(
    t["name"] for t in (*YOUTUBE_TOOLS, *TIKTOK_TOOLS, *MOVIE_TOOLS, *UTIL_TOOLS)
)

_SCHEMAS: dict[str, dict] = {
    tool["name"]: tool["parameters"]
    for tool in (*(RAG_TOOLS if RAG_ENABLED else []), *YOUTUBE_TOOLS, *TIKTOK_TOOLS, *MOVIE_TOOLS, *UTIL_TOOLS)
}


def _unwrap_data_miner_result(result: Any, name: str) -> dict:
    if isinstance(result, dict):
        if result.get("success") is True and isinstance(result.get("data"), (dict, list)):
            return result["data"]
        if result.get("success") is False:
            return {"error": result.get("error") or "data-miner request failed", "tool": name}
    return result if isinstance(result, dict) else {"data": result}


async def _execute_http_tool(name: str, inputs: dict) -> dict:
    fn = TOOL_HANDLERS.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return _unwrap_data_miner_result(await fn(inputs), name)
    except Exception as exc:
        return {"error": str(exc), "tool": name}


async def _execute_mcp_tool(name: str, inputs: dict) -> dict:
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
    schema = _SCHEMAS.get(name)
    if schema:
        try:
            jsonschema.validate(instance=inputs, schema=schema)
        except jsonschema.ValidationError as exc:
            return {"error": f"Invalid input for {name}: {exc.message}"}

    if name in _RAG_TOOL_NAMES:
        if not is_rag_enabled():
            return rag_disabled_error()
        return _unwrap_data_miner_result(await TOOL_HANDLERS[name](inputs), name)

    if AGENT_CRAWL_BACKEND == "mcp" and name in _CRAWL_TOOL_NAMES:
        return await _execute_mcp_tool(name, inputs)

    return await _execute_http_tool(name, inputs)
