"""Programmatic Phoenix MCP calls (hackathon path without LLM feedback agent)."""

from __future__ import annotations

from typing import Any

from clintrace_agent.config import USE_PHOENIX_MCP, USE_PHOENIX_MCP_REMOTE, USE_PHOENIX_MCP_STDIO
from clintrace_agent.phoenix_mcp_connection import (
    PHOENIX_MCP_URL,
    phoenix_mcp_http_headers,
)


async def probe_phoenix_mcp_list_traces(*, limit: int = 5) -> dict[str, Any] | None:
    """Call Phoenix MCP ``list-traces`` once; traced via OpenInference MCP.

    Args:
        limit: Max traces to request from the MCP server.

    Returns:
        Raw MCP tool result dict, or None when MCP is disabled/unconfigured.
    """
    if not USE_PHOENIX_MCP:
        return None

    if USE_PHOENIX_MCP_REMOTE:
        return await _probe_http(limit=limit)
    if USE_PHOENIX_MCP_STDIO:
        return await _probe_stdio(limit=limit)
    return None


async def _probe_http(*, limit: int) -> dict[str, Any] | None:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    headers = phoenix_mcp_http_headers()
    try:
        async with streamablehttp_client(
            PHOENIX_MCP_URL,
            headers=headers,
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("list-traces", {"limit": limit})
                if result.isError:
                    return None
                content = result.content
                if not content:
                    return None
                first = content[0]
                text = getattr(first, "text", None) or str(first)
                return {"tool": "list-traces", "limit": limit, "preview": text[:500]}
    except Exception:  # noqa: BLE001 — MCP optional; REST feedback still runs
        return None


async def _probe_stdio(*, limit: int) -> dict[str, Any] | None:
    import os

    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    base_url = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "").rstrip("/")
    api_key = os.getenv("PHOENIX_API_KEY", "")
    if not base_url or not api_key:
        return None

    server_params = StdioServerParameters(
        command="npx",
        args=[
            "-y",
            "@arizeai/phoenix-mcp@latest",
            "--baseUrl",
            base_url,
            "--apiKey",
            api_key,
        ],
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "list-traces",
                    {"limit": limit},
                )
                if result.isError:
                    return None
                content = result.content
                if not content:
                    return None
                first = content[0]
                text = getattr(first, "text", None) or str(first)
                return {"tool": "list-traces", "limit": limit, "preview": text[:500]}
    except Exception:  # noqa: BLE001 — MCP optional; REST feedback still runs
        return None
