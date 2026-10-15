"""Map LLM retrieval scope to Pinecone metadata filters.

corpusTopic on vectors is the slug of the first path segment under source_data/
(see pinecone-pipeline/corpus_metadata.py ROOT_TOPIC_SLUGS). Keep enum values in sync.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Slugs must match pinecone-pipeline/corpus_metadata.ROOT_TOPIC_SLUGS (same order as documented roots).
TOPIC_1_NAJEM_I = "1_najem_instytucjonalny"
TOPIC_2_NAJEM_F = "2_najem_firma"
TOPIC_3_VAT = "3_mieszkania_z_vatem_najem_zwyky"
TOPIC_4_REZERWACJA = "4_umowa_rezerwacyjna"
TOPIC_5_INSTRUKCJE = "5_instrukcje"
TOPIC_6_NORTHWIND = "6_program_rabatowy_northwind_club_i_smart_home"
TOPIC_ZAKWATEROWANIE = "zakwaterowanie"


class RetrievalScope(str, Enum):
    """Closed set for structured output; one value per top-level corpus folder + all."""

    ALL = "all"
    NAJEM_INSTYTUCJONALNY = TOPIC_1_NAJEM_I
    NAJEM_FIRMA = TOPIC_2_NAJEM_F
    MIESZKANIA_Z_VATEM = TOPIC_3_VAT
    UMOWA_REZERWACYJNA = TOPIC_4_REZERWACJA
    INSTRUKCJE = TOPIC_5_INSTRUKCJE
    PROGRAM_NORTHWIND_CLUB = TOPIC_6_NORTHWIND
    ZAKWATEROWANIE = TOPIC_ZAKWATEROWANIE


def pinecone_filter_for_scope(scope: RetrievalScope) -> Optional[Dict[str, Any]]:
    """
    Build Pinecone metadata filter for query() / LangChain retriever.

    Returns None when the whole namespace should be searched (no filter).
    """
    if scope == RetrievalScope.ALL:
        return None
    return {"corpusTopic": scope.value}


def pinecone_filter_for_scopes(scopes: List[RetrievalScope]) -> Optional[Dict[str, Any]]:
    """
    OR across corpusTopic values. If the list is empty or contains ``all``, return None (no topic filter).
    """
    if not scopes:
        return None
    if any(s == RetrievalScope.ALL for s in scopes):
        return None
    seen: list[str] = []
    for scope in scopes:
        value = scope.value
        if value not in seen:
            seen.append(value)
    if len(seen) == 1:
        return {"corpusTopic": seen[0]}
    return {"$or": [{"corpusTopic": topic_value} for topic_value in seen]}


def merge_pinecone_filters(
    base: Optional[Dict[str, Any]],
    extra: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Combine a scope filter (or None) with an additional metadata constraint.

    Pinecone requires $and when both filters are present.
    """
    if not base:
        return dict(extra)
    return {"$and": [base, extra]}


def merge_corpus_path_prefix(
    scope_filter: Optional[Dict[str, Any]],
    corpus_path_prefix: str,
) -> Optional[Dict[str, Any]]:
    """
    Narrow retrieval to vectors whose corpusPathPrefix matches (two path segments, slug form).

    See pinecone-pipeline/corpus_metadata.corpusPathPrefix.
    """
    prefix = corpus_path_prefix.strip()
    if not prefix:
        return scope_filter
    extra: Dict[str, Any] = {"corpusPathPrefix": prefix}
    if scope_filter is None:
        return extra
    return {"$and": [scope_filter, extra]}


def merge_corpus_path_prefixes_or(
    base: Optional[Dict[str, Any]],
    prefixes: List[str],
) -> Optional[Dict[str, Any]]:
    """OR across corpusPathPrefix values (multiple subfolder two-segment slugs)."""
    cleaned = [p.strip() for p in prefixes if p and str(p).strip()]
    uniq = list(dict.fromkeys(cleaned))
    if not uniq:
        return base
    if len(uniq) == 1:
        extra: Dict[str, Any] = {"corpusPathPrefix": uniq[0]}
    else:
        extra = {"$or": [{"corpusPathPrefix": prefix_value} for prefix_value in uniq]}
    if base is None:
        return extra
    return {"$and": [base, extra]}


def build_pinecone_filter_for_retrieval(
    scopes: List[RetrievalScope],
    *,
    corpus_path_prefixes: Optional[List[str]] = None,
    corpus_file_name: str = "",
    corpus_source_relative_path: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Compose metadata filter: OR on corpusTopic, OR on corpusPathPrefix, optional exact file/path.
    """
    base = pinecone_filter_for_scopes(scopes)
    prefix_list = corpus_path_prefixes or []
    base = merge_corpus_path_prefixes_or(base, prefix_list)
    file_name = corpus_file_name.strip()
    rel_path = corpus_source_relative_path.strip().replace("\\", "/")
    if file_name:
        base = merge_pinecone_filters(base, {"fileName": file_name})
    if rel_path:
        base = merge_pinecone_filters(base, {"sourceRelativePath": rel_path})
    return base


def coalesce_retrieval_scopes_from_state(state: dict) -> List[RetrievalScope]:
    """Read retrieval_scopes list from graph state; fall back to legacy retrieval_scope string."""
    raw = state.get("retrieval_scopes")
    if raw is None:
        legacy = state.get("retrieval_scope")
        if legacy:
            raw = [legacy] if isinstance(legacy, str) else legacy
        else:
            raw = [RetrievalScope.ALL.value]
    elif isinstance(raw, str):
        raw = [raw]
    out: List[RetrievalScope] = []
    for item in raw:
        if item is None:
            continue
        slug = str(item).strip()
        if not slug:
            continue
        try:
            out.append(RetrievalScope(slug))
        except ValueError:
            logger.warning("Unknown retrieval scope slug %r; ignoring", item)
    if not out:
        return [RetrievalScope.ALL]
    if any(scope == RetrievalScope.ALL for scope in out):
        return [RetrievalScope.ALL]
    return out


def coalesce_path_prefixes_from_state(state: dict) -> List[str]:
    """Read corpus_path_prefixes list; fall back to legacy corpus_path_prefix string."""
    prefixes = state.get("corpus_path_prefixes")
    if prefixes is None:
        prefixes = []
    if isinstance(prefixes, str):
        prefixes = [prefixes] if prefixes.strip() else []
    cleaned = [str(p).strip() for p in prefixes if p and str(p).strip()]
    legacy = (state.get("corpus_path_prefix") or "").strip()
    if legacy and legacy not in cleaned:
        cleaned.insert(0, legacy)
    return list(dict.fromkeys(cleaned))


def pinecone_filter_chunk_rows_only(scope: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Restrict dense search to chunk rows, not summary routing vectors.

    Matches ``summaries=false`` (explicit) or missing ``summaries`` (legacy upserts).
    """
    chunk_only: Dict[str, Any] = {
        "$or": [
            {"summaries": False},
            {"summaries": {"$exists": False}},
        ]
    }
    if scope is None:
        return chunk_only
    return {"$and": [scope, chunk_only]}
