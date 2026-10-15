"""Retrieval score merge, sort, and CONTEXT formatting."""

from __future__ import annotations

from langchain_core.documents import Document

from rag.anchor_documents import (
    RETRIEVAL_SCORE_METADATA_KEY,
    merge_retrieval_candidates_by_score,
    sort_documents_by_retrieval_score,
)
from rag.nodes import format_docs_numbered


def _doc(content: str, doc_id: str, chunk: int, score: float) -> Document:
    return Document(
        page_content=content,
        metadata={
            "docId": doc_id,
            "chunkIndex": chunk,
            "fileName": f"{doc_id}.pdf",
            "sourceRelativePath": f"corpus/{doc_id}.pdf",
            RETRIEVAL_SCORE_METADATA_KEY: score,
        },
    )


def test_merge_keeps_higher_score_on_duplicate_chunk() -> None:
    shared = _doc("anchor", "doc-a", 0, 0.55)
    higher_main = _doc("main", "doc-a", 0, 0.82)
    merged = merge_retrieval_candidates_by_score([shared], [higher_main])
    assert len(merged) == 1
    assert merged[0].page_content == "main"
    assert merged[0].metadata[RETRIEVAL_SCORE_METADATA_KEY] == 0.82


def test_merge_orders_by_score_descending() -> None:
    low = _doc("low", "doc-a", 0, 0.40)
    high = _doc("high", "doc-b", 1, 0.91)
    merged = merge_retrieval_candidates_by_score([low], [high])
    assert merged[0].page_content == "high"
    assert merged[1].page_content == "low"


def test_sort_puts_unscored_last() -> None:
    unscored = Document(page_content="x", metadata={"docId": "u", "chunkIndex": 0})
    scored = _doc("y", "s", 1, 0.5)
    ordered = sort_documents_by_retrieval_score([unscored, scored])
    assert ordered[0].page_content == "y"


def test_format_docs_numbered_includes_relevance_score() -> None:
    text = format_docs_numbered([_doc("body", "d", 0, 0.77)])
    assert "Trafność wyszukiwania: 0.770" in text
    assert "**Fragment 1**" in text
