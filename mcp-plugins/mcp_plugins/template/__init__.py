"""Minimal stdlib HTTP MCP-shaped server template."""

from mcp_plugins.template.server import McpHttpServer, ToolSpec, build_default_tools, main

__all__ = ["McpHttpServer", "ToolSpec", "build_default_tools", "main"]
