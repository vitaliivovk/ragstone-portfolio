"""Parse RAG_TURN_AUDIT payloads (offline fixtures; no Azure)."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Union

AuditPayload = Dict[str, Any]


def parse_audit_payload(raw: Union[str, Mapping[str, Any]]) -> AuditPayload:
    """
    Accept a dict, a JSON object string, or an App Insights-style log line
    ``RAG_TURN_AUDIT {...json...}``.
    """
    if isinstance(raw, Mapping):
        payload = dict(raw)
    else:
        text = raw.strip()
        if text.startswith("RAG_TURN_AUDIT"):
            # Drop event prefix; remainder is JSON.
            text = text[len("RAG_TURN_AUDIT") :].strip()
        payload = json.loads(text)

    if payload.get("event") not in (None, "RAG_TURN_AUDIT"):
        raise ValueError(f"unexpected event: {payload.get('event')!r}")
    return payload


def load_audit_list(data: Union[List[Any], Mapping[str, Any]]) -> List[AuditPayload]:
    """Normalize fixture root: bare list, or ``{\"audits\": [...]}``."""
    if isinstance(data, list):
        return [parse_audit_payload(item) for item in data]
    if isinstance(data, Mapping) and "audits" in data:
        return [parse_audit_payload(item) for item in data["audits"]]
    raise ValueError("fixture must be a list of audits or {\"audits\": [...]}")


def corpus_path_prefix(source_relative_path: str, *, depth: int = 1) -> Optional[str]:
    """First path segment(s) under the corpus tree (folder slug signal)."""
    parts = [p for p in source_relative_path.replace("\\", "/").split("/") if p]
    if not parts:
        return None
    return "/".join(parts[: max(1, depth)])


def feature_key(audit: Mapping[str, Any]) -> str:
    """Coarse clustering signature for recurring task patterns."""
    topic = str(audit.get("answer_topic") or "none")
    scope = str(audit.get("retrieval_scope") or "unknown")
    prefixes: List[str] = []
    for doc in audit.get("retrieved_documents") or []:
        if not isinstance(doc, Mapping):
            continue
        path = doc.get("sourceRelativePath") or ""
        prefix = corpus_path_prefix(str(path))
        if prefix and prefix not in prefixes:
            prefixes.append(prefix)
        if len(prefixes) >= 3:
            break
    prefix_part = ",".join(sorted(prefixes)) or "_"
    return f"{topic}|{scope}|{prefix_part}"
