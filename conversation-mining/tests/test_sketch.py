"""Unit tests for offline conversation-mining sketches (no Azure)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conversation_mining.audit import feature_key, parse_audit_payload
from conversation_mining.sketch import (
    load_audit_fixture,
    sketches_from_audits,
    to_promotable_definition,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample_rag_turn_audits.json"


def test_parse_audit_log_line() -> None:
    payload = {"event": "RAG_TURN_AUDIT", "channel": "web", "conversation_id": "c1"}
    line = "RAG_TURN_AUDIT " + json.dumps(payload)
    parsed = parse_audit_payload(line)
    assert parsed["channel"] == "web"
    assert parsed["conversation_id"] == "c1"


def test_fixture_yields_deposit_reply_candidate() -> None:
    audits = load_audit_fixture(FIXTURE)
    assert len(audits) == 4

    sketches = sketches_from_audits(audits, channel="web", min_conversations=2)
    assert len(sketches) == 1
    sketch = sketches[0]
    assert sketch["status"] == "candidate"
    assert sketch["id"] == "deposit_reply"
    assert sketch["mining"]["conversation_count"] == 2
    assert sketch["output_template"]["never_send"] is True
    assert sketch["steps"][0]["type"] == "rag_query"
    assert sketch["steps"][1]["type"] == "llm_transform"


def test_teams_channel_excluded_by_default() -> None:
    audits = load_audit_fixture(FIXTURE)
    # Only the two web deposit_reply turns should cluster; teams twin is ignored.
    keys = {feature_key(a) for a in audits if a.get("channel") == "web" and a.get("response_path") != "smalltalk"}
    assert len(keys) == 1


def test_to_promotable_strips_mining_metadata() -> None:
    sketches = sketches_from_audits(load_audit_fixture(FIXTURE))
    promotable = to_promotable_definition(sketches[0])
    assert "status" not in promotable
    assert "mining" not in promotable
    assert promotable["output_template"]["never_send"] is True


def test_min_conversations_filters_singletons() -> None:
    audits = load_audit_fixture(FIXTURE)
    # Raise threshold so nothing qualifies.
    assert sketches_from_audits(audits, min_conversations=3) == []


def test_optional_process_engine_validate() -> None:
    pytest.importorskip("process_engine")
    from process_engine.schema import validate_process_dict

    sketch = sketches_from_audits(load_audit_fixture(FIXTURE))[0]
    # Candidate versions may need a catalog-friendly bump before promote.
    promotable = to_promotable_definition(sketch)
    promotable["version"] = "0.1.0"
    validate_process_dict(promotable)
