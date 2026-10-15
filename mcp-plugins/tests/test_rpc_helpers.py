"""Pure RPC helper tests for the template server (no bind / no network I/O)."""

from __future__ import annotations

import json

from mcp_plugins.common.policy import ToolScope
from mcp_plugins.sharepoint.server import build_sharepoint_tools
from mcp_plugins.teams.server import build_teams_tools
from mcp_plugins.template.server import McpHttpServer, build_default_tools


def test_tools_list_includes_template_ping() -> None:
    server = McpHttpServer(plugin_name="template", tools=build_default_tools())
    resp = server.handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, {})
    names = {t["name"] for t in resp["result"]["tools"]}
    assert "template_ping" in names
    assert "template_forbidden_send" in names


def test_send_tool_call_denied() -> None:
    server = McpHttpServer(plugin_name="template", tools=build_default_tools())
    resp = server.handle_rpc(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "template_forbidden_send", "arguments": {}},
        },
        {},
    )
    assert resp["result"]["isError"] is True
    body = json.loads(resp["result"]["content"][0]["text"])
    assert body["error"] == "scope_denied"
    assert body["reason"] == "never_send_v1"


def test_sharepoint_and_teams_catalog_scopes() -> None:
    sp = {t.name: t.scope for t in build_sharepoint_tools()}
    assert sp["sharepoint_list_sites"] is ToolScope.SEARCH
    assert sp["sharepoint_browse_folder"] is ToolScope.READ
    assert sp["sharepoint_read_file"] is ToolScope.READ

    tm = {t.name: t.scope for t in build_teams_tools()}
    assert tm["teams_post_message"] is ToolScope.SEND
    assert tm["teams_draft_message"] is ToolScope.DRAFT
