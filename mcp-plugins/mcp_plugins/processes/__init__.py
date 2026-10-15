"""Process-engine MCP tool wrappers (Phase 4).

Registers list_processes / run_process against the process-engine package.
Requires ``ragstone-process-engine`` installed (sibling ``process-engine/``).
"""

from __future__ import annotations

from typing import Any, List, Mapping

from mcp_plugins.common.policy import ToolScope
from mcp_plugins.template.server import ToolSpec, _stub_ok


def build_process_tools() -> List[ToolSpec]:
    """Build ToolSpec list for the stdlib MCP HTTP stub server."""
    try:
        from process_engine.mcp_tools import handle_tool_call
    except ImportError as exc:  # pragma: no cover - env without process-engine
        raise ImportError(
            "process_engine is required for process MCP tools. "
            "Install sibling package: pip install -e ../process-engine"
        ) from exc

    def list_handler(arguments: Mapping[str, Any], _headers: Mapping[str, str]) -> Any:
        return handle_tool_call("list_processes", arguments)

    def run_handler(arguments: Mapping[str, Any], _headers: Mapping[str, str]) -> Any:
        result = handle_tool_call("run_process", arguments)
        # Never claim send; artifact is draft-only.
        if isinstance(result, dict) and result.get("artifact"):
            art = result["artifact"]
            if art.get("artifact_type") == "email_draft" and art.get("never_send") is not True:
                return _stub_ok("blocked", error="never_send_v1")
        return result

    return [
        ToolSpec(
            name="list_processes",
            description=(
                "List versioned process definitions (shared templates + tenant filter)."
            ),
            scope=ToolScope.READ,
            input_schema={
                "type": "object",
                "properties": {
                    "tenant_id": {"type": "string"},
                    "latest_only": {"type": "boolean", "default": True},
                },
            },
            handler=list_handler,
        ),
        ToolSpec(
            name="run_process",
            description=(
                "Dry-run a process by id; returns draft artifacts only (never sends email)."
            ),
            scope=ToolScope.DRAFT,
            input_schema={
                "type": "object",
                "required": ["process_id"],
                "properties": {
                    "process_id": {"type": "string"},
                    "version": {"type": "string"},
                    "inputs": {"type": "object", "additionalProperties": True},
                },
            },
            handler=run_handler,
        ),
    ]
