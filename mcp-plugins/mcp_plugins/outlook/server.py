"""Outlook MCP plugin stub (Graph mail).

Read / search / draft only in v1. Live send is registered for signature
completeness but denied by never-send policy (TASKS #14 / #14c).

No live Graph HTTP in this scaffold — OBO + consent required later.
"""

from __future__ import annotations

from typing import Any, List, Mapping

from mcp_plugins.common.policy import ToolScope
from mcp_plugins.template.server import ToolSpec, main


def _stub(op: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "stub": True,
        "op": op,
        "message": "Outlook Graph client not wired; OBO / Mail.* consent pending.",
        "args": dict(arguments),
        "auth_notes": {
            "delegated": "OBO — Mail.Read / Mail.ReadWrite for draft; never Mail.Send in v1",
        },
    }


def build_outlook_tools() -> List[ToolSpec]:
    return [
        ToolSpec(
            name="outlook_search_messages",
            description="Search the signed-in user's mailbox (search).",
            scope=ToolScope.SEARCH,
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "KQL / Graph $search fragment",
                    },
                    "folder": {
                        "type": "string",
                        "description": "Optional well-known folder (inbox, drafts, …)",
                    },
                    "top": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                "required": ["query"],
            },
            handler=lambda a, _h: _stub("search_messages", a),
        ),
        ToolSpec(
            name="outlook_read_message",
            description="Read a single message metadata + body preview (read).",
            scope=ToolScope.READ,
            input_schema={
                "type": "object",
                "properties": {
                    "message_id": {"type": "string"},
                    "include_attachments_meta": {"type": "boolean"},
                },
                "required": ["message_id"],
            },
            handler=lambda a, _h: _stub("read_message", a),
        ),
        ToolSpec(
            name="outlook_draft_message",
            description=(
                "Create or update a draft email for human review (draft). "
                "Does not send. Prefer this over any send tool in v1."
            ),
            scope=ToolScope.DRAFT,
            input_schema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Recipient email addresses",
                    },
                    "cc": {"type": "array", "items": {"type": "string"}},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "reply_to_message_id": {
                        "type": "string",
                        "description": "Optional Graph message id when drafting a reply",
                    },
                },
                "required": ["subject", "body"],
            },
            handler=lambda a, _h: _stub("draft_message", a),
        ),
        ToolSpec(
            name="outlook_send_message",
            description=(
                "PLACEHOLDER — live send. Denied by v1 never-send policy until "
                "explicitly enabled (TASKS #14)."
            ),
            scope=ToolScope.SEND,
            input_schema={
                "type": "object",
                "properties": {
                    "draft_id": {"type": "string"},
                    "message_id": {"type": "string"},
                },
            },
            handler=lambda a, _h: _stub("send_message", a),
        ),
    ]


def run(host: str = "127.0.0.1", port: int = 8094) -> None:
    main(plugin_name="outlook", tools=build_outlook_tools(), host=host, port=port)


if __name__ == "__main__":
    run()
