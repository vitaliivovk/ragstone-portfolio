"""Structured audit logging for RAG turns (searchable in Azure Application Insights / Log Analytics)."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

# Kusto: traces | where message startswith "RAG_TURN_AUDIT"
AUDIT_EVENT = "RAG_TURN_AUDIT"


def context_chunk_ids_from_sources(sources: List[Dict[str, Any]]) -> List[str]:
    """``docId:chunkIndex`` rows actually present in source metadata (LLM context / citations)."""
    chunk_ids: List[str] = []
    for src in sources:
        doc_id = src.get("docId")
        chunk_idx = src.get("chunkIndex")
        if doc_id is None or chunk_idx is None:
            continue
        chunk_ids.append(f"{doc_id}:{int(chunk_idx)}")
    return chunk_ids


def _compact_sources(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep citation-relevant fields only (avoid huge payloads)."""
    keys = (
        "sourceRelativePath",
        "fileName",
        "chunkIndex",
        "docId",
        "pageNumber",
        "slideNumber",
        "sheetName",
        "sectionTitle",
    )
    out: List[Dict[str, Any]] = []
    for src in sources:
        row: Dict[str, Any] = {}
        for key in keys:
            if key in src and src[key] is not None:
                row[key] = src[key]
        if row:
            out.append(row)
    return out


def log_rag_turn_audit(
    logger: logging.Logger,
    *,
    teams_user_id: str,
    teams_user_name: str,
    user_message: str,
    assistant_response: str,
    needs_rag: bool,
    optimized_query: str,
    retrieval_scope: str,
    search_focus: str,
    optimizer_reasoning: str,
    pinecone_index: str,
    pinecone_namespace: str,
    pinecone_metadata_filter: Optional[Dict[str, Any]],
    retrieval_k: int,
    retrieval_fallback_unfiltered: bool,
    retrieved_sources: List[Dict[str, Any]],
    corpus_path_prefixes: Optional[List[str]] = None,
    azure_invocation_id: str = "",
    answer_depth: str = "",
    output_truncated_by_max_tokens: bool = False,
    reuse_previous_context: str = "none",
    optimizer_saw_cached_retrieval: bool = False,
    cached_retrieval_age_min: Optional[float] = None,
    cached_retrieval_files: Optional[List[str]] = None,
    conversation_id: str = "",
    response_path: str = "",
    clarification_needed: bool = False,
    clarification_questions: Optional[List[str]] = None,
    answer_topic: str = "none",
    numeric_answer_first: bool = False,
    context_chunk_ids: Optional[List[str]] = None,
    channel: str = "teams",
) -> None:
    """
    Emit one JSON log line per user turn. Azure Monitor ingests this as a trace when
    APPLICATIONINSIGHTS_CONNECTION_STRING is set on the Function App.

    ``channel`` is ``teams`` (default) or ``web`` (LibreChat / OpenAI-compat adapter).
    For web, ``teams_user_id`` holds the Entra object id (header ``X-User-ID``).
    """
    payload: Dict[str, Any] = {
        "event": AUDIT_EVENT,
        "channel": channel or "teams",
        "azure_invocation_id": azure_invocation_id,
        "teams_user_id": teams_user_id,
        "teams_user_name": teams_user_name,
        "conversation_id": conversation_id or "",
        "user_message": user_message,
        "assistant_response": assistant_response,
        "needs_rag": needs_rag,
        "optimized_query": optimized_query,
        "retrieval_scope": retrieval_scope,
        "search_focus": search_focus,
        "optimizer_reasoning": optimizer_reasoning,
        "pinecone_index": pinecone_index,
        "pinecone_namespace": pinecone_namespace,
        "pinecone_metadata_filter": pinecone_metadata_filter,
        "retrieval_k": retrieval_k,
        "retrieval_fallback_unfiltered": retrieval_fallback_unfiltered,
        "retrieved_document_count": len(retrieved_sources),
        "retrieved_documents": _compact_sources(retrieved_sources),
        "assistant_response_chars": len(assistant_response or ""),
        "answer_depth": answer_depth or "",
        "output_truncated_by_max_tokens": output_truncated_by_max_tokens,
        "reuse_previous_context": reuse_previous_context or "none",
        "optimizer_saw_cached_retrieval": optimizer_saw_cached_retrieval,
        "response_path": response_path or "",
        "clarification_needed": clarification_needed,
        "clarification_questions": list(clarification_questions or []),
        "answer_topic": answer_topic or "none",
        "numeric_answer_first": numeric_answer_first,
        "context_chunk_ids": list(context_chunk_ids or []),
    }
    if cached_retrieval_age_min is not None:
        payload["cached_retrieval_age_min"] = round(cached_retrieval_age_min, 2)
    if cached_retrieval_files:
        payload["cached_retrieval_files"] = list(cached_retrieval_files)
    if corpus_path_prefixes:
        payload["corpus_path_prefixes"] = list(corpus_path_prefixes)
    line = json.dumps(payload, ensure_ascii=False)
    logger.info("%s %s", AUDIT_EVENT, line)
