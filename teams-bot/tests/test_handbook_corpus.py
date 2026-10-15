"""Handbook corpus loader for direct_mode=handbook (synthetic fixture; real corpus is local-only)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import rag.handbook as handbook
from rag.handbook import handbook_direct_enabled, handbook_token_count, load_handbook_text

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "handbook_corpus.sample.json"


@pytest.fixture(autouse=True)
def _sample_corpus(monkeypatch):
    monkeypatch.setenv("RAG_HANDBOOK_CORPUS_PATH", str(FIXTURE))
    monkeypatch.setattr(handbook, "_CACHE_BLOB", None)
    monkeypatch.setattr(handbook, "_TOKEN_COUNT", None)


def test_handbook_corpus_fixture_has_keys() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert "instrukcja_dla_nowego_pracownika_2025" in data


def test_load_handbook_text_contains_headers() -> None:
    text = load_handbook_text()
    assert "=== Instrukcja dla nowego pracownika 2025 ===" in text
    assert "=== Procesy NW RENT 2025 ===" not in text


def test_handbook_token_count_positive() -> None:
    assert handbook_token_count() > 0


def test_missing_corpus_raises(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RAG_HANDBOOK_CORPUS_PATH", str(tmp_path / "missing.json"))
    with pytest.raises(FileNotFoundError):
        load_handbook_text()


def test_handbook_direct_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("RAG_HANDBOOK_DIRECT_ENABLED", raising=False)
    assert handbook_direct_enabled() is False


def test_handbook_direct_enabled_when_env_one(monkeypatch) -> None:
    monkeypatch.setenv("RAG_HANDBOOK_DIRECT_ENABLED", "1")
    assert handbook_direct_enabled() is True
