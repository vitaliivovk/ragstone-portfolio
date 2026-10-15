"""Salesforce MCP plugin stub.

Lookup placeholders only — separate OAuth (not Entra OBO). No live SF API
in this scaffold. Harvest Onyx CE Salesforce connector patterns later (MIT core only).
"""

from __future__ import annotations

from typing import Any, List, Mapping

from mcp_plugins.common.policy import ToolScope
from mcp_plugins.template.server import ToolSpec, main


def _stub(op: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "stub": True,
        "op": op,
        "message": "Salesforce client not wired; connected-app OAuth pending.",
        "args": dict(arguments),
        "auth_notes": {
            "oauth": "Per-tenant Salesforce Connected App (not Entra OBO)",
            "scopes": "api / refresh_token — least privilege; no write in v1 stub",
        },
    }


def build_salesforce_tools() -> List[ToolSpec]:
    return [
        ToolSpec(
            name="salesforce_search",
            description="SOSL / global search placeholder across objects the app can see (search).",
            scope=ToolScope.SEARCH,
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "object_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional object API names (Account, Contact, …)",
                    },
                    "top": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                "required": ["query"],
            },
            handler=lambda a, _h: _stub("search", a),
        ),
        ToolSpec(
            name="salesforce_lookup_record",
            description="Fetch a single record by Id or external key (read).",
            scope=ToolScope.READ,
            input_schema={
                "type": "object",
                "properties": {
                    "object_type": {"type": "string"},
                    "record_id": {"type": "string"},
                    "external_id_field": {"type": "string"},
                    "external_id": {"type": "string"},
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional field list; default safe subset later",
                    },
                },
                "required": ["object_type"],
            },
            handler=lambda a, _h: _stub("lookup_record", a),
        ),
        ToolSpec(
            name="salesforce_list_related",
            description="List related records for a parent Id (read).",
            scope=ToolScope.READ,
            input_schema={
                "type": "object",
                "properties": {
                    "object_type": {"type": "string"},
                    "record_id": {"type": "string"},
                    "relationship": {"type": "string"},
                    "top": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                "required": ["object_type", "record_id", "relationship"],
            },
            handler=lambda a, _h: _stub("list_related", a),
        ),
        # No create/update/delete in v1 stub catalog.
    ]


def run(host: str = "127.0.0.1", port: int = 8095) -> None:
    main(plugin_name="salesforce", tools=build_salesforce_tools(), host=host, port=port)


if __name__ == "__main__":
    run()
