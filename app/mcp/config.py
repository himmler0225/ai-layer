"""MCP client configuration."""

import os
from enum import Enum


class MCPTransport(str, Enum):
    STDIO = "stdio"
    SSE = "sse"


AGENT_CRAWL_BACKEND: str = os.getenv("AGENT_CRAWL_BACKEND", "http").strip().lower()
MCP_TRANSPORT = MCPTransport(os.getenv("MCP_TRANSPORT", "sse"))
MCP_SSE_URL = os.getenv("MCP_SSE_URL", "http://data-miner:8000/mcp/sse")
MCP_SERVICE_TOKEN = os.getenv("MCP_SERVICE_TOKEN", "") or os.getenv("DATA_MINER_SERVICE_TOKEN", "")

# Chỉ dùng khi MCP_TRANSPORT=stdio (local dev, Cursor)
MCP_STDIO_COMMAND = os.getenv("MCP_STDIO_COMMAND", "python")
MCP_STDIO_ARGS = os.getenv("MCP_STDIO_ARGS", "-m app.mcp.server").split()
