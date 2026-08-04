"""Phoenix MCP connection helpers — remote HTTP (Cloud Run) or local stdio."""

from __future__ import annotations

import os
from typing import Any

from clintrace_agent.config import (
    PHOENIX_MCP_SERVICE_KEY,
    PHOENIX_MCP_URL,
    USE_PHOENIX_MCP_REMOTE,
    USE_PHOENIX_MCP_STDIO,
)

PHOENIX_MCP_TOOL_FILTER = [
    "list-traces",
    "get-trace",
    "get-spans",
    "get-span-annotations",
]


def normalize_phoenix_mcp_url(url: str) -> str:
    """Ensure URL ends with /mcp for Streamable HTTP transport."""
    raw = url.strip().rstrip("/")
    if not raw:
        return ""
    if raw.endswith("/mcp"):
        return raw
    return f"{raw}/mcp"


def phoenix_mcp_http_headers() -> dict[str, str] | None:
    """Optional Bearer auth for the ClinTrace MCP Cloud Run service."""
    if not PHOENIX_MCP_SERVICE_KEY:
        return None
    return {"Authorization": f"Bearer {PHOENIX_MCP_SERVICE_KEY}"}


def build_phoenix_mcp_toolset() -> Any | None:
    """Return ADK McpToolset for remote HTTP or local stdio, or None if disabled."""
    if USE_PHOENIX_MCP_REMOTE:
        return _http_toolset()
    if USE_PHOENIX_MCP_STDIO:
        return _stdio_toolset()
    return None


def _http_toolset() -> Any:
    from google.adk.tools.mcp_tool import McpToolset
    from google.adk.tools.mcp_tool.mcp_session_manager import (
        StreamableHTTPConnectionParams,
    )

    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=PHOENIX_MCP_URL,
            headers=phoenix_mcp_http_headers(),
            timeout=30.0,
            sse_read_timeout=300.0,
        ),
        tool_filter=PHOENIX_MCP_TOOL_FILTER,
    )


def _stdio_toolset() -> Any:
    from google.adk.tools.mcp_tool import McpToolset
    from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
    from mcp import StdioServerParameters

    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="npx",
                args=[
                    "-y",
                    "@arizeai/phoenix-mcp@latest",
                    "--baseUrl",
                    os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", ""),
                    "--apiKey",
                    os.environ.get("PHOENIX_API_KEY", ""),
                ],
            )
        ),
        tool_filter=PHOENIX_MCP_TOOL_FILTER,
    )
