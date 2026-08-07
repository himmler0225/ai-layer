import json
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client

from app.mcp.config import (
    MCP_SERVICE_TOKEN,
    MCP_STDIO_ARGS,
    MCP_STDIO_COMMAND,
    MCP_TRANSPORT,
    MCPTransport,
    mcp_sse_url,
)


@asynccontextmanager
async def mcp_session():
    """Open and initialize an MCP client session, over SSE or stdio depending
    on `MCP_TRANSPORT`, closing it automatically on exit."""
    if MCP_TRANSPORT == MCPTransport.SSE:
        headers = {"Authorization": f"Bearer {MCP_SERVICE_TOKEN}"} if MCP_SERVICE_TOKEN else {}
        async with sse_client(url=mcp_sse_url(), headers=headers) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
    else:
        params = StdioServerParameters(command=MCP_STDIO_COMMAND, args=MCP_STDIO_ARGS)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session


async def list_tools() -> list[dict]:
    """List the tools exposed by the MCP server.

    Returns:
        A list of tool definitions as plain dicts (via `model_dump()`)."""
    async with mcp_session() as session:
        result = await session.list_tools()
        return [t.model_dump() for t in result.tools]


async def call_tool(name: str, arguments: dict) -> dict:
    """Invoke a named MCP tool and parse its JSON text response.

    Args:
        name: The MCP tool name to call.
        arguments: JSON-serializable arguments to pass to the tool.

    Returns:
        The tool's parsed JSON response. If the response is empty, returns
        `{"success": False, "error": "empty MCP response", "tool": name}`; if
        the response text isn't valid JSON, returns
        `{"success": False, "error": "invalid JSON from MCP", "tool": name,
        "raw": raw}`."""
    async with mcp_session() as session:
        result = await session.call_tool(name, arguments=arguments)
        if not result.content:
            return {"success": False, "error": "empty MCP response", "tool": name}
        raw = result.content[0].text
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"success": False, "error": "invalid JSON from MCP", "tool": name, "raw": raw}
