"""Unit tests for MCP_TOOL_AUDIT formatting (no network)."""

from __future__ import annotations

import json

from mcp_plugins.common.audit import format_mcp_tool_audit


def test_audit_line_shape() -> None:
    line = format_mcp_tool_audit(
        plugin="sharepoint",
        tool="sharepoint_browse_folder",
        scope="read",
        status="stub",
        duration_ms=3,
        tenant_id="t1",
        user_oid="oid-1",
        conversation_id="c1",
        detail={"path": "AI/v3"},
    )
    payload = json.loads(line)
    assert payload["event"] == "MCP_TOOL_AUDIT"
    assert payload["plugin"] == "sharepoint"
    assert payload["tool"] == "sharepoint_browse_folder"
    assert payload["scope"] == "read"
    assert payload["status"] == "stub"
    assert payload["tenant_id"] == "t1"
    assert payload["user_oid"] == "oid-1"
    assert payload["conversation_id"] == "c1"
    assert payload["duration_ms"] == 3
    assert payload["http_status"] is None
    assert payload["detail"] == {"path": "AI/v3"}
    assert "token" not in line.lower()
