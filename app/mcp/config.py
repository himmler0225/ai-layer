"""MCP client configuration."""

import os
from enum import Enum

import app.config.settings as settings


class MCPTransport(str, Enum):
    STDIO = "stdio"
    SSE = "sse"


AGENT_CRAWL_BACKEND: str = os.getenv("AGENT_CRAWL_BACKEND", "http").strip().lower()
MCP_TRANSPORT = MCPTransport(os.getenv("MCP_TRANSPORT", "sse"))
MCP_SERVICE_TOKEN = os.getenv("MCP_SERVICE_TOKEN", "") or os.getenv("MCP_AUTH_TOKEN", "") or os.getenv(
    "DATA_MINER_SERVICE_TOKEN", ""
)

# Chỉ dùng khi MCP_TRANSPORT=stdio (local dev, Cursor)
MCP_STDIO_COMMAND = os.getenv("MCP_STDIO_COMMAND", "python")
MCP_STDIO_ARGS = os.getenv("MCP_STDIO_ARGS", "-m app.mcp.server").split()


def mcp_sse_url() -> str:
    explicit = (os.getenv("MCP_SSE_URL") or os.getenv("DATA_MINER_MCP_URL") or "").strip()
    if explicit:
        return explicit
    base = (settings.DATA_MINER_URL or "").rstrip("/")
    if base:
        return f"{base}/mcp/sse"
    return "http://localhost:8000/mcp/sse"


MCP_SSE_URL = mcp_sse_url()
