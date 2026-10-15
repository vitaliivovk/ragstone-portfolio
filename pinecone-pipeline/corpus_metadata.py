"""Derive Pinecone filter metadata from sourceRelativePath (mirrors source_data layout).

corpusTopic is the slug of the **first path segment** (top-level folder under the corpus root),
e.g. ``1_najem_instytucjonalny``. This scales with new root folders without one-off rules.

Slug values must match teams-bot/rag/retrieval_filter.py RetrievalScope (except ``all``).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Final, List, Tuple


def _path_segment_slug(segment: str) -> str:
    normalized = unicodedata.normalize("NFKD", segment)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    return slug or "segment"


# Expected first-segment labels under source_data/ (corpus root layout).
# If the corpus adds a new root folder, append it here and add matching RetrievalScope in the bot.
SOURCE_DATA_ROOT_SEGMENTS: Final[Tuple[str, ...]] = (
    "1 Najem Instytucjonalny",
    "2 Najem Firma",
    "3 Mieszkania z vatem- najem zwykły",
    "4 Umowa rezerwacyjna",
    "5 Instrukcje",
    "6 Program rabatowy NORTHWIND CLUB i SMART HOME",
    "Zakwaterowanie",
)

ROOT_TOPIC_SLUGS: Final[Tuple[str, ...]] = tuple(
    _path_segment_slug(s) for s in SOURCE_DATA_ROOT_SEGMENTS
)


def _path_parts(source_relative_path: str) -> List[str]:
    if not source_relative_path or not source_relative_path.strip():
        return []
    normalized = source_relative_path.replace("\\", "/").strip("/")
    return [part for part in normalized.split("/") if part.strip()]


def derive_corpus_metadata(source_relative_path: str) -> Dict[str, Any]:
    """
    Build metadata fields for Pinecone filtering.

    - corpusTopic: slug of the first path segment (product / top-level library folder).
    - corpusTopFolder: same as corpusTopic (stable alias for tooling).
    - corpusPathPrefix: first two segments slugified (sub-area, e.g. the local power company vs OWU).
    """
    parts = _path_parts(source_relative_path)
    if not parts:
        return {
            "corpusTopic": "unknown_root",
            "corpusTopFolder": "unknown_root",
        }

    top_slug = _path_segment_slug(parts[0])
    out: Dict[str, Any] = {
        "corpusTopic": top_slug,
        "corpusTopFolder": top_slug,
    }
    if len(parts) >= 2:
        out["corpusPathPrefix"] = (
            f"{_path_segment_slug(parts[0])}/{_path_segment_slug(parts[1])}"
        )
    return out
