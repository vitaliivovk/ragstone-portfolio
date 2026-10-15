"""Teams MCP plugin stub.

Replying in the *current* Teams bot chat stays on Bot Framework (existing).
This plugin is for Graph-backed read/post against chats/channels the user can access
via OBO — TASKS #14c. No live Graph in this scaffold.
"""

from __future__ import annotations

from typing import Any, List, Mapping

from mcp_plugins.common.policy import ToolScope
from mcp_plugins.template.server import ToolSpec, main


def _stub(op: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "stub": True,
        "op": op,
        "message": "Teams Graph client not wired; OBO / consent pending.",
        "args": dict(arguments),
    }


def build_teams_tools() -> List[ToolSpec]:
    return [
        ToolSpec(
            name="teams_list_chats",
            description="List recent chats visible to the signed-in user (search).",
            scope=ToolScope.SEARCH,
            input_schema={
                "type": "object",
                "properties": {
                    "top": {"type": "integer", "minimum": 1, "maximum": 50},
                },
            },
            handler=lambda a, _h: _stub("list_chats", a),
        ),
        ToolSpec(
            name="teams_read_messages",
            description="Read recent messages from a chat or channel thread (read).",
            scope=ToolScope.READ,
            input_schema={
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string"},
                    "channel_id": {"type": "string"},
                    "team_id": {"type": "string"},
                    "top": {"type": "integer", "minimum": 1, "maximum": 50},
                },
            },
            handler=lambda a, _h: _stub("read_messages", a),
        ),
        ToolSpec(
            name="teams_draft_message",
            description="Prepare a message draft payload for human review (draft). Does not post.",
            scope=ToolScope.DRAFT,
            input_schema={
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string"},
                    "channel_id": {"type": "string"},
                    "team_id": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["body"],
            },
            handler=lambda a, _h: _stub("draft_message", a),
        ),
        ToolSpec(
            name="teams_post_message",
            description="PLACEHOLDER — live post. Denied by v1 never-send policy until explicitly enabled.",
            scope=ToolScope.SEND,
            input_schema={
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["chat_id", "body"],
            },
            handler=lambda a, _h: _stub("post_message", a),
        ),
    ]


def run(host: str = "127.0.0.1", port: int = 8092) -> None:
    main(plugin_name="teams", tools=build_teams_tools(), host=host, port=port)


if __name__ == "__main__":
    run()
