"""Always-on semantic retrieval from fixed handbook paths (merged with scoped RAG)."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document

from .pinecone_ids import chunk_vector_id
from .retrieval_filter import pinecone_filter_chunk_rows_only

# Paths match Pinecone ``sourceRelativePath`` (under ``pinecone-pipeline/source_data/``).
_DEFAULT_ANCHOR_SOURCE_RELATIVE_PATHS: tuple[str, ...] = (
    "5 Instrukcje/Instrukcja dla nowego pracownika 2025.pdf",
)


def anchor_retrieval_enabled() -> bool:
    raw = os.environ.get("RAG_ANCHOR_RETRIEVAL_ENABLED", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def anchor_source_relative_paths() -> list[str]:
    override = os.environ.get("RAG_ANCHOR_SOURCE_RELATIVE_PATHS", "").strip()
    if override:
        return [p.strip().replace("\\", "/") for p in override.split(",") if p.strip()]
    return list(_DEFAULT_ANCHOR_SOURCE_RELATIVE_PATHS)


def anchor_retrieval_k() -> int:
    raw = os.environ.get("RAG_ANCHOR_CHUNK_K", "6").strip()
    parsed = int(raw)
    return max(1, min(24, parsed))


def anchor_chunk_filter(paths: list[str]) -> Optional[Dict[str, Any]]:
    """Metadata filter: chunk rows only, ``sourceRelativePath`` in given list."""
    if not paths:
        return None
    if len(paths) == 1:
        path_clause: Dict[str, Any] = {"sourceRelativePath": paths[0]}
    else:
        path_clause = {"$or": [{"sourceRelativePath": p} for p in paths]}
    return pinecone_filter_chunk_rows_only(path_clause)


def chunk_dedupe_key(doc: Document) -> str:
    meta = doc.metadata
    doc_id = meta.get("docId")
    chunk_idx = meta.get("chunkIndex")
    if doc_id is not None and chunk_idx is not None:
        return chunk_vector_id(str(doc_id), int(chunk_idx))
    path = str(meta.get("sourceRelativePath") or "")
    return f"path:{path}:chunk:{chunk_idx}"


RETRIEVAL_SCORE_METADATA_KEY = "retrievalScore"
NEIGHBOR_RETRIEVAL_SCORE_FACTOR = 0.98


def retrieval_score_from_document(doc: Document) -> float:
    """Pinecone/LangChain similarity score attached at retrieval time; higher = closer match."""
    raw = doc.metadata.get(RETRIEVAL_SCORE_METADATA_KEY)
    if raw is None:
        return -1.0
    return float(raw)


def merge_retrieval_candidates_by_score(
    anchor_docs: list[Document],
    main_docs: list[Document],
) -> list[Document]:
    """
    Merge anchor + primary hits, dedupe by chunk id (keep higher score), sort by score descending.
    """
    by_key: dict[str, Document] = {}
    for doc in anchor_docs + main_docs:
        key = chunk_dedupe_key(doc)
        score = retrieval_score_from_document(doc)
        existing = by_key.get(key)
        if existing is None or retrieval_score_from_document(existing) < score:
            by_key[key] = doc
    merged = list(by_key.values())
    merged.sort(key=retrieval_score_from_document, reverse=True)
    return merged


def sort_documents_by_retrieval_score(docs: list[Document]) -> list[Document]:
    """Stable sort: highest retrieval score first; unscored rows last."""
    return sorted(docs, key=retrieval_score_from_document, reverse=True)


def merge_anchor_then_main(anchor_docs: list[Document], main_docs: list[Document]) -> list[Document]:
    """Deprecated name — merges by retrieval score, not anchor-first order."""
    return merge_retrieval_candidates_by_score(anchor_docs, main_docs)
