"""MCP tool signatures for process engine exposure (thin stubs).

These helpers return JSON-serializable payloads matching the shape
LibreChat / mcp-plugins would wrap with tools/list + tools/call.

Registration sketch (see README)::

    from process_engine.mcp_tools import LIST_PROCESSES_TOOL, RUN_PROCESS_TOOL, handle_tool_call
    # wire into mcp_plugins.template.server.ToolSpec with scope DRAFT for run_process
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from process_engine.catalog import ProcessCatalog, ProcessNotFound
from process_engine.runner import ProcessRunner, dry_run


LIST_PROCESSES_TOOL = {
    "name": "list_processes",
    "description": (
        "List versioned process definitions available to the caller "
        "(shared templates + optional tenant-scoped entries)."
    ),
    "scope": "read",
    "input_schema": {
        "type": "object",
        "properties": {
            "tenant_id": {
                "type": "string",
                "description": "Optional tenant filter; shared templates always included.",
            },
            "latest_only": {
                "type": "boolean",
                "default": True,
            },
        },
    },
}


RUN_PROCESS_TOOL = {
    "name": "run_process",
    "description": (
        "Dry-run (or later: execute) a process by id. "
        "Produces artifacts only — email drafts never auto-send in v1."
    ),
    "scope": "draft",
    "input_schema": {
        "type": "object",
        "required": ["process_id"],
        "properties": {
            "process_id": {"type": "string"},
            "version": {
                "type": "string",
                "description": "Optional; defaults to latest catalog version.",
            },
            "inputs": {
                "type": "object",
                "additionalProperties": True,
                "description": "Map of process input name -> value.",
            },
        },
    },
}


def list_processes(
    catalog: ProcessCatalog,
    *,
    tenant_id: Optional[str] = None,
    latest_only: bool = True,
) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for definition in catalog.list_processes(tenant_id=tenant_id, latest_only=latest_only):
        items.append(
            {
                "id": definition.id,
                "version": definition.version,
                "title": definition.title,
                "description": definition.description,
                "tenant_id": definition.tenant_id,
                "inputs": [inp.model_dump() for inp in definition.inputs],
            }
        )
    return {"processes": items}


def run_process(
    catalog: ProcessCatalog,
    *,
    process_id: str,
    version: Optional[str] = None,
    inputs: Mapping[str, Any] | None = None,
    runner: Optional[ProcessRunner] = None,
) -> Dict[str, Any]:
    try:
        definition = catalog.get(process_id, version)
    except ProcessNotFound as exc:
        return {"ok": False, "error": f"ProcessNotFound: {exc}"}

    result = dry_run(definition, inputs or {}, runner=runner)
    return {
        "ok": result.ok,
        "process_id": result.process_id,
        "version": result.version,
        "artifact": result.artifact,
        "steps": [
            {"step_id": t.step_id, "step_type": t.step_type, "output": t.output}
            for t in result.steps
        ],
        "error": result.error,
    }


def handle_tool_call(
    name: str,
    arguments: Mapping[str, Any],
    *,
    catalog: Optional[ProcessCatalog] = None,
    runner: Optional[ProcessRunner] = None,
) -> Dict[str, Any]:
    """Dispatch list_processes / run_process for MCP tools/call stubs."""
    cat = catalog or ProcessCatalog()
    if name == "list_processes":
        return list_processes(
            cat,
            tenant_id=arguments.get("tenant_id"),
            latest_only=bool(arguments.get("latest_only", True)),
        )
    if name == "run_process":
        process_id = arguments.get("process_id")
        if not process_id:
            return {"ok": False, "error": "process_id is required"}
        return run_process(
            cat,
            process_id=str(process_id),
            version=arguments.get("version"),
            inputs=arguments.get("inputs") or {},
            runner=runner,
        )
    return {"ok": False, "error": f"unknown tool: {name}"}
