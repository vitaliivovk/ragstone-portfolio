"""Tests for handbook anchor merge and dedupe keys."""

from langchain_core.documents import Document

from rag.anchor_documents import (
    RETRIEVAL_SCORE_METADATA_KEY,
    chunk_dedupe_key,
    merge_retrieval_candidates_by_score,
)


def test_merge_dedupes_and_sorts_by_score_not_anchor_order() -> None:
    shared_meta = {
        "docId": "doc-a",
        "chunkIndex": 0,
        "sourceRelativePath": "5 Instrukcje/a.pdf",
        RETRIEVAL_SCORE_METADATA_KEY: 0.5,
    }
    anchor = [Document(page_content="anchor text", metadata=dict(shared_meta))]
    main = [
        Document(
            page_content="better dup",
            metadata={**shared_meta, RETRIEVAL_SCORE_METADATA_KEY: 0.9},
        ),
        Document(
            page_content="other",
            metadata={
                "docId": "doc-a",
                "chunkIndex": 1,
                "sourceRelativePath": "5 Instrukcje/a.pdf",
                RETRIEVAL_SCORE_METADATA_KEY: 0.7,
            },
        ),
    ]
    merged = merge_retrieval_candidates_by_score(anchor, main)
    assert len(merged) == 2
    assert merged[0].page_content == "better dup"
    assert merged[1].page_content == "other"


def test_chunk_dedupe_key_stable() -> None:
    doc = Document(
        page_content="x",
        metadata={"docId": "d1", "chunkIndex": 3, "sourceRelativePath": "p.pdf"},
    )
    assert chunk_dedupe_key(doc) == chunk_dedupe_key(doc)
