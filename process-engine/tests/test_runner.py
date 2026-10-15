"""Dry-run runner unit tests (mocked callouts)."""

from __future__ import annotations

from process_engine.catalog import ProcessCatalog
from process_engine.mcp_tools import handle_tool_call, list_processes, run_process
from process_engine.runner import ProcessRunner, dry_run, render_template
from process_engine.schema import validate_process_dict


EXAMPLE_INPUTS = {
    "client_name": "Acme Sp. z o.o.",
    "client_email": "kontakt@acme.example",
    "topic": "procedura kaucji",
    "question": "Jak wygląda zwrot kaucji?",
}


def test_render_template() -> None:
    assert render_template("Hello {{name}}", {"name": "Ada"}) == "Hello Ada"


def test_dry_run_standard_client_reply() -> None:
    definition = ProcessCatalog().get("standard_client_reply")
    result = dry_run(definition, EXAMPLE_INPUTS)
    assert result.ok, result.error
    assert result.artifact["artifact_type"] == "email_draft"
    assert result.artifact["never_send"] is True
    assert "Acme" in result.artifact["subject"]
    assert result.artifact["body"]
    assert [t.step_type for t in result.steps] == [
        "rag_query",
        "plugin_call",
        "llm_transform",
    ]


def test_missing_required_input_fails() -> None:
    definition = ProcessCatalog().get("standard_client_reply")
    result = dry_run(definition, {"client_name": "X"})
    assert not result.ok
    assert "missing required input" in (result.error or "")


def test_mcp_list_and_run() -> None:
    catalog = ProcessCatalog()
    listed = list_processes(catalog)
    assert any(p["id"] == "standard_client_reply" for p in listed["processes"])

    out = run_process(
        catalog,
        process_id="standard_client_reply",
        inputs=EXAMPLE_INPUTS,
    )
    assert out["ok"] is True
    assert out["artifact"]["never_send"] is True

    via_dispatch = handle_tool_call(
        "run_process",
        {"process_id": "standard_client_reply", "inputs": EXAMPLE_INPUTS},
        catalog=catalog,
    )
    assert via_dispatch["ok"] is True


def test_plugin_mock_blocks_send_scope() -> None:
    runner = ProcessRunner()
    definition = validate_process_dict(
        {
            "id": "would_send",
            "version": "1",
            "title": "bad",
            "inputs": [],
            "steps": [
                {
                    "id": "s",
                    "type": "plugin_call",
                    "plugin": "outlook",
                    "tool": "send",
                    # schema forbids send — use draft then call mock with send via client
                    "scope": "draft",
                    "arguments": {},
                }
            ],
            "output_template": {
                "artifact_type": "text",
                "body_template": "ok",
                "never_send": True,
            },
        }
    )
    # Direct client guard:
    try:
        runner.plugins.call("outlook", "send", {}, scope="send")
        raised = False
    except PermissionError:
        raised = True
    assert raised

    ok = dry_run(definition, {}, runner=runner)
    assert ok.ok
