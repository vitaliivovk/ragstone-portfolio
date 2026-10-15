"""Catalog load/list unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from process_engine.catalog import ProcessCatalog, ProcessNotFound, load_process


def test_bundled_catalog_loads_standard_client_reply() -> None:
    catalog = ProcessCatalog()
    definition = catalog.get("standard_client_reply")
    assert definition.version == "1"
    assert definition.output_template.never_send is True
    assert any(s.type == "rag_query" for s in definition.steps)


def test_list_includes_shared_templates() -> None:
    catalog = ProcessCatalog()
    listed = catalog.list_processes()
    ids = {d.id for d in listed}
    assert "standard_client_reply" in ids


def test_get_missing_raises() -> None:
    catalog = ProcessCatalog()
    with pytest.raises(ProcessNotFound):
        catalog.get("no_such_process")


def test_load_process_from_path() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "process_engine"
        / "catalog"
        / "standard_client_reply"
        / "1.json"
    )
    definition = load_process(path)
    assert definition.id == "standard_client_reply"


def test_id_folder_mismatch_rejected(tmp_path: Path) -> None:
    proc = tmp_path / "wrong_folder"
    proc.mkdir()
    (proc / "1.json").write_text(
        '{"id":"other_id","version":"1","title":"x","steps":'
        '[{"id":"s","type":"rag_query","query_template":"q"}],'
        '"output_template":{"artifact_type":"text","body_template":"b","never_send":true}}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="does not match folder"):
        ProcessCatalog(tmp_path)
