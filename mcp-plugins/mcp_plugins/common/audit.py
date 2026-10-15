"""MCP_TOOL_AUDIT line helpers — never include tokens or bodies."""

from __future__ import annotations

import json
from typing import Any, Mapping, MutableMapping, Optional


def format_mcp_tool_audit(
    *,
    plugin: str,
    tool: str,
    scope: str,
    status: str,
    duration_ms: int = 0,
    tenant_id: str = "",
    user_oid: str = "",
    conversation_id: str = "",
    http_status: Optional[int] = None,
    detail: Optional[Mapping[str, Any]] = None,
) -> str:
    """Return a single-line JSON audit event suitable for stdout / App Insights.

    ``status`` should be one of: ok | denied | error | stub.
    ``detail`` must not contain secrets, file contents, or message bodies.
    """
    payload: MutableMapping[str, Any] = {
        "event": "MCP_TOOL_AUDIT",
        "plugin": plugin,
        "tool": tool,
        "scope": scope,
        "tenant_id": tenant_id or "",
        "user_oid": user_oid or "",
        "conversation_id": conversation_id or "",
        "status": status,
        "http_status": http_status,
        "duration_ms": int(duration_ms),
        "detail": dict(detail) if detail else {},
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
