#!/usr/bin/env python3
"""
Validate a Pinecone namespace before / after summary routing rollout (plan §1.5).

Uses describe_index_stats, a sample similarity query, and optional fetch-by-id probes.
Requires PINECONE_API_KEY, OPENAI_API_KEY, PINECONE_INDEX_NAME (or PINECONE_INDEX), PINECONE_NAMESPACE.

Usage (from repo root or pinecone-pipeline):

    cd pinecone-pipeline
    uv run python scripts/validate_pinecone_namespace.py

Optional:

    SAMPLE_IDS="docid:0000,docid:0001" uv run python scripts/validate_pinecone_namespace.py
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from typing import Any, Dict, List

from dotenv import load_dotenv


def _load_dotenv() -> None:
    pipeline_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root = os.path.dirname(pipeline_dir)
    for candidate in (
        os.environ.get("DOTENV_PATH", "").strip(),
        os.path.join(root, ".env"),
        os.path.join(pipeline_dir, ".env"),
    ):
        if candidate and os.path.isfile(candidate):
            load_dotenv(candidate)
            return
    load_dotenv()


def _index_name() -> str:
    for key in ("PINECONE_INDEX_NAME", "PINECONE_INDEX"):
        raw = os.environ.get(key, "").strip()
        if raw:
            return raw
    raise RuntimeError("Set PINECONE_INDEX_NAME or PINECONE_INDEX")


def _namespace() -> str:
    raw = os.environ.get("PINECONE_NAMESPACE", "").strip()
    if not raw:
        raise RuntimeError("Set PINECONE_NAMESPACE")
    return raw


def _sample_query_embedding() -> List[float]:
    from pinecone_io import MODEL_NAME, get_openai

    client = get_openai()
    probe = os.environ.get("PINECONE_VALIDATE_QUERY", "umowa najmu opłaty procedura").strip()
    res = client.embeddings.create(model=MODEL_NAME, input=[probe])
    return list(res.data[0].embedding)


def _parse_sample_ids() -> List[str]:
    raw = os.environ.get("SAMPLE_IDS", "").strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def main() -> int:
    _load_dotenv()
    try:
        from pinecone_io import get_index, get_pinecone
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from pinecone_io import get_index, get_pinecone

    index_name = _index_name()
    namespace = _namespace()
    pc = get_pinecone()
    index = get_index(pc, index_name)

    print(f"Index: {index_name!r}  Namespace: {namespace!r}")
    stats = index.describe_index_stats()
    ns_stats = None
    if hasattr(stats, "namespaces") and stats.namespaces:
        ns_stats = stats.namespaces.get(namespace)
    total = getattr(ns_stats, "vector_count", None) if ns_stats else None
    if total is None:
        print("Namespace stats: (no per-namespace breakdown in response)")
    else:
        print(f"Namespace vector_count (reported): {total}")

    vector = _sample_query_embedding()
    sample = index.query(
        vector=vector,
        top_k=40,
        namespace=namespace,
        include_metadata=True,
    )
    matches = list(sample.matches) if sample and sample.matches else []
    print(f"Sample query hits: {len(matches)}")

    summaries_hist: Counter[str] = Counter()
    chunk_core = {"docId": 0, "chunkIndex": 0, "corpusTopic": 0, "text": 0}
    summary_core = {"docId": 0, "chunkIndexStart": 0, "chunkIndexEnd": 0, "corpusTopic": 0, "text": 0}
    chunk_rows = 0
    summary_rows = 0
    for match in matches:
        meta: Dict[str, Any] = dict(match.metadata) if match.metadata else {}
        if meta.get("summaries") is True:
            summary_rows += 1
            summaries_hist["true"] += 1
            for field in summary_core:
                if meta.get(field) is not None and str(meta.get(field)).strip() != "":
                    summary_core[field] += 1
        elif "summaries" not in meta:
            summaries_hist["missing"] += 1
            chunk_rows += 1
            for field in chunk_core:
                if meta.get(field) is not None and str(meta.get(field)).strip() != "":
                    chunk_core[field] += 1
        else:
            summaries_hist["false"] += 1
            chunk_rows += 1
            for field in chunk_core:
                if meta.get(field) is not None and str(meta.get(field)).strip() != "":
                    chunk_core[field] += 1

    print(f"Among sample hits — summary rows: {summary_rows}, chunk-like rows: {chunk_rows}")
    print(f"summaries metadata histogram (true/false/missing): {dict(summaries_hist)}")
    print(f"Chunk rows — metadata coverage (of {chunk_rows}): {chunk_core}")
    if summary_rows:
        print(f"Summary rows — metadata coverage (of {summary_rows}): {summary_core}")

    if summary_rows == 0 and summaries_hist["missing"] + summaries_hist["false"] > 0:
        print(
            "Note: No summaries=true in sample. Chunk-only search is expected until "
            "GENERATE_SUMMARIES ingest completes."
        )

    sample_ids = _parse_sample_ids()
    if sample_ids:
        fetched = index.fetch(ids=sample_ids, namespace=namespace)
        vectors = getattr(fetched, "vectors", None) or {}
        print(f"Fetch probe: requested {len(sample_ids)}, returned {len(vectors)}")
        for vid, row in vectors.items():
            meta = dict(row.metadata) if row.metadata else {}
            print(f"  id={vid!r} summaries={meta.get('summaries', '<<missing>>')!r}")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
