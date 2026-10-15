"""Packaged employee handbook text for the direct-mode (no Pinecone) path."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import tiktoken

logger = logging.getLogger(__name__)

# The handbook JSON is gitignored (built locally from private corpus); override with RAG_HANDBOOK_CORPUS_PATH.
_DEFAULT_CORPUS_PATH = Path(__file__).resolve().parent / "handbook_corpus.json"
_CACHE_BLOB: str | None = None
_TOKEN_COUNT: int | None = None


def handbook_direct_enabled() -> bool:
    """When false, handbook routing is coerced to full RAG in :meth:`RAGNodes.optimize`."""
    raw = os.environ.get("RAG_HANDBOOK_DIRECT_ENABLED", "0").strip().lower()
    return raw not in ("0", "false", "no", "off")


def handbook_corpus_path() -> Path:
    override = os.environ.get("RAG_HANDBOOK_CORPUS_PATH", "").strip()
    return Path(override) if override else _DEFAULT_CORPUS_PATH


def load_handbook_text() -> str:
    """
    Return the handbook anchor document as one string (header + deduped body text).

    Raises:
        FileNotFoundError: if ``handbook_corpus.json`` was not built.
    """
    global _CACHE_BLOB
    if _CACHE_BLOB is not None:
        return _CACHE_BLOB
    path = handbook_corpus_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"Handbook corpus not found at {path}. Run: python scripts/build_handbook_corpus.py"
        )
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    instr_key = "instrukcja_dla_nowego_pracownika_2025"
    instr = data[instr_key]
    _CACHE_BLOB = f"=== Instrukcja dla nowego pracownika 2025 ===\n\n{instr}"
    return _CACHE_BLOB


def handbook_token_count() -> int:
    """Approximate token count of :func:`load_handbook_text` (gpt-4o cl100k-based encoding)."""
    global _TOKEN_COUNT
    if _TOKEN_COUNT is not None:
        return _TOKEN_COUNT
    text = load_handbook_text()
    encoding = tiktoken.encoding_for_model("gpt-4o")
    _TOKEN_COUNT = len(encoding.encode(text))
    return _TOKEN_COUNT


def log_handbook_token_budget() -> None:
    """Log once at process startup when handbook direct mode may be used."""
    if not handbook_direct_enabled():
        logger.info("RAG_HANDBOOK_DIRECT_ENABLED is off; handbook routing will fall back to RAG.")
        return
    try:
        token_estimate = handbook_token_count()
    except FileNotFoundError:
        logger.warning(
            "Handbook corpus missing (%s); handbook direct path unavailable until built.",
            handbook_corpus_path(),
        )
        return
    if token_estimate > 60_000:
        logger.warning(
            "Handbook corpus token estimate (%s) exceeds 60000; review corpus size.",
            token_estimate,
        )
    else:
        logger.info("Handbook corpus token estimate: %s", token_estimate)
