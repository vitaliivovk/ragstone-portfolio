"""SharePoint MCP plugin stub.

Auth modes (do not mix casually):

1. **Delegated / OBO (worker UI)** — signed-in user sees only what Graph allows for them.
   Typical delegated scopes to request later: `Sites.Read.All` or site-scoped equivalents,
   `Files.Read.All`. Wire via LibreChat `obo:` / forwarded user token (TASKS #14c).

2. **Application `Sites.Selected` (headless bot)** — TASKS #35. Admin consent + per-site
   write grant for corpus/smoke paths under `AI/`. Not used for "chat as the user" browse.

This module exposes tool **signatures** and stub handlers only — no Graph HTTP.
"""

from __future__ import annotations

from typing import Any, List, Mapping

from mcp_plugins.common.policy import ToolScope
from mcp_plugins.template.server import ToolSpec, main


def _stub(op: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "stub": True,
        "op": op,
        "message": "SharePoint Graph client not wired; admin consent / OBO pending.",
        "args": dict(arguments),
        "auth_notes": {
            "delegated": "OBO — Sites/Files read for signed-in user (TASKS #14c)",
            "application": "Sites.Selected + per-site grant (TASKS #35) for headless write",
        },
    }


def build_sharepoint_tools() -> List[ToolSpec]:
    return [
        ToolSpec(
            name="sharepoint_list_sites",
            description="List SharePoint sites visible to the caller (search/list).",
            scope=ToolScope.SEARCH,
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Optional site name / URL fragment filter",
                    },
                    "top": {"type": "integer", "minimum": 1, "maximum": 50},
                },
            },
            handler=lambda a, _h: _stub("list_sites", a),
        ),
        ToolSpec(
            name="sharepoint_browse_folder",
            description="Browse children of a document library folder (list).",
            scope=ToolScope.READ,
            input_schema={
                "type": "object",
                "properties": {
                    "site_id": {"type": "string"},
                    "drive_id": {"type": "string"},
                    "path": {
                        "type": "string",
                        "description": "Folder path relative to drive root, e.g. AI/v3",
                    },
                },
                "required": ["site_id", "path"],
            },
            handler=lambda a, _h: _stub("browse_folder", a),
        ),
        ToolSpec(
            name="sharepoint_read_file",
            description="Read file metadata and text/content preview (read). No upload in v1 stub.",
            scope=ToolScope.READ,
            input_schema={
                "type": "object",
                "properties": {
                    "site_id": {"type": "string"},
                    "drive_id": {"type": "string"},
                    "item_id": {"type": "string"},
                    "path": {"type": "string"},
                    "max_bytes": {"type": "integer", "minimum": 1},
                },
            },
            handler=lambda a, _h: _stub("read_file", a),
        ),
        # Upload/write stays out of the default catalog until TASKS #35 + feature flag.
        # When added: scope=DRAFT or a dedicated write policy; never unbounded delete.
    ]


def run(host: str = "127.0.0.1", port: int = 8091) -> None:
    main(plugin_name="sharepoint", tools=build_sharepoint_tools(), host=host, port=port)


if __name__ == "__main__":
    run()
