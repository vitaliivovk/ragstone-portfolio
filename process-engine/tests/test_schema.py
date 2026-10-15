"""Schema validation unit tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from process_engine.schema import (
    ProcessDefinition,
    validate_process_dict,
)


def _minimal(**overrides):
    base = {
        "id": "demo_process",
        "version": "1",
        "title": "Demo",
        "inputs": [{"name": "q", "type": "string", "required": True}],
        "steps": [
            {
                "id": "r1",
                "type": "rag_query",
                "query_template": "{{q}}",
            }
        ],
        "output_template": {
            "artifact_type": "email_draft",
            "subject_template": "Hi",
            "body_template": "Body {{q}}",
            "never_send": True,
        },
    }
    base.update(overrides)
    return base


def test_valid_minimal_definition() -> None:
    d = validate_process_dict(_minimal())
    assert d.id == "demo_process"
    assert d.catalog_key() == "demo_process@1"
    assert d.output_template.never_send is True


def test_rejects_email_draft_with_send_allowed() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_process_dict(
            _minimal(
                output_template={
                    "artifact_type": "email_draft",
                    "body_template": "x",
                    "never_send": False,
                }
            )
        )
    assert "never_send" in str(exc.value)


def test_rejects_duplicate_step_ids() -> None:
    with pytest.raises(ValidationError):
        validate_process_dict(
            _minimal(
                steps=[
                    {"id": "same", "type": "rag_query", "query_template": "a"},
                    {"id": "same", "type": "rag_query", "query_template": "b"},
                ]
            )
        )


def test_rejects_unknown_llm_input_refs() -> None:
    with pytest.raises(ValidationError):
        validate_process_dict(
            _minimal(
                steps=[
                    {
                        "id": "compose",
                        "type": "llm_transform",
                        "prompt_template": "x",
                        "input_refs": ["missing_step"],
                    }
                ]
            )
        )


def test_rejects_send_scope_on_plugin_step() -> None:
    with pytest.raises(ValidationError):
        validate_process_dict(
            _minimal(
                steps=[
                    {
                        "id": "bad",
                        "type": "plugin_call",
                        "plugin": "outlook",
                        "tool": "send_mail",
                        "scope": "send",
                        "arguments": {},
                    }
                ]
            )
        )


def test_rejects_invalid_id_pattern() -> None:
    with pytest.raises(ValidationError):
        validate_process_dict(_minimal(id="Bad-Id"))


def test_json_schema_export() -> None:
    schema = ProcessDefinition.model_json_schema()
    assert "properties" in schema
    assert "id" in schema["properties"]
