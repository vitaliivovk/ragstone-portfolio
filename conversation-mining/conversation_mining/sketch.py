"""Cluster RAG_TURN_AUDIT turns into candidate process sketches (no Azure)."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from conversation_mining.audit import AuditPayload, feature_key, load_audit_list, parse_audit_payload

_SLUG_RE = re.compile(r"[^a-z0-9_]+")


def _slugify(text: str, *, fallback: str = "mined_process") -> str:
    raw = (text or "").strip().lower().replace("-", "_").replace(" ", "_")
    slug = _SLUG_RE.sub("_", raw).strip("_")
    if not slug or not slug[0].isalpha():
        slug = f"{fallback}_{slug}".strip("_") or fallback
    return slug[:48]


def load_audit_fixture(path: Path | str) -> List[AuditPayload]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return load_audit_list(data)


def _eligible(audit: Mapping[str, Any], *, channel: Optional[str]) -> bool:
    if channel is not None and str(audit.get("channel") or "") != channel:
        return False
    if not str(audit.get("conversation_id") or "").strip():
        return False
    path = str(audit.get("response_path") or "")
    if path in ("smalltalk",):
        return False
    return True


def cluster_audits(
    audits: Sequence[Mapping[str, Any]],
    *,
    channel: Optional[str] = "web",
    min_conversations: int = 2,
) -> Dict[str, List[AuditPayload]]:
    """Group eligible audits by feature key; keep clusters with enough conversations."""
    buckets: Dict[str, List[AuditPayload]] = defaultdict(list)
    for raw in audits:
        audit = parse_audit_payload(raw)
        if not _eligible(audit, channel=channel):
            continue
        buckets[feature_key(audit)].append(audit)

    out: Dict[str, List[AuditPayload]] = {}
    for key, members in buckets.items():
        conv_ids = {str(m.get("conversation_id")) for m in members}
        if len(conv_ids) >= min_conversations:
            out[key] = members
    return out


def _representative_query(members: Sequence[Mapping[str, Any]]) -> str:
    for m in members:
        q = str(m.get("optimized_query") or "").strip()
        if q:
            return q
    for m in members:
        q = str(m.get("user_message") or "").strip()
        if q:
            return q
    return "Summarize the recurring user request"


def sketch_from_cluster(
    key: str,
    members: Sequence[Mapping[str, Any]],
    *,
    version: str = "0.1.0-candidate",
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Emit a dict shaped like process_engine.ProcessDefinition (candidate, not catalogued).

    Does not import process-engine (optional later validation by the operator).
    """
    topic, scope, _prefixes = (key.split("|", 2) + ["none", "unknown", "_"])[:3]
    process_id = _slugify(topic if topic != "none" else scope, fallback="mined_task")
    query = _representative_query(members)
    conv_count = len({str(m.get("conversation_id")) for m in members})

    rag_step_id = "gather_context"
    compose_step_id = "compose_reply"

    return {
        "id": process_id,
        "version": version,
        "tenant_id": tenant_id,
        "title": f"Mined: {topic if topic != 'none' else scope}",
        "description": (
            f"Candidate from conversation mining ({conv_count} conversations, "
            f"feature_key={key!r}). Human review required before catalog promotion."
        ),
        "inputs": [
            {
                "name": "client_request",
                "type": "text",
                "description": "User request / client question to answer in standard form",
                "required": True,
            }
        ],
        "steps": [
            {
                "id": rag_step_id,
                "type": "rag_query",
                "query_template": "{{client_request}}",
                "top_k": 5,
                "namespace_hint": None,
            },
            {
                "id": compose_step_id,
                "type": "llm_transform",
                "prompt_template": (
                    "Using the retrieved context, draft a standard reply for:\n"
                    "{{client_request}}\n\n"
                    f"Pattern observed in audits (example optimized_query): {query}"
                ),
                "input_refs": [rag_step_id],
            },
        ],
        "output_template": {
            "artifact_type": "email_draft",
            "subject_template": "Re: {{client_request}}",
            "body_template": "{{compose_reply}}",
            "never_send": True,
        },
        # Mining metadata (strip before validate_process_dict / catalog write)
        "status": "candidate",
        "mining": {
            "feature_key": key,
            "conversation_count": conv_count,
            "turn_count": len(members),
            "sample_retrieval_scope": scope,
            "sample_answer_topic": topic,
        },
    }


def sketches_from_audits(
    audits: Iterable[Mapping[str, Any]],
    *,
    channel: Optional[str] = "web",
    min_conversations: int = 2,
    version: str = "0.1.0-candidate",
    tenant_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Cluster audits and return candidate process sketches."""
    clustered = cluster_audits(
        list(audits),
        channel=channel,
        min_conversations=min_conversations,
    )
    sketches = [
        sketch_from_cluster(key, members, version=version, tenant_id=tenant_id)
        for key, members in sorted(clustered.items())
    ]
    return sketches


def to_promotable_definition(sketch: Mapping[str, Any]) -> Dict[str, Any]:
    """Drop mining-only fields so the dict can be validated by process-engine."""
    allowed = {
        "id",
        "version",
        "tenant_id",
        "title",
        "description",
        "inputs",
        "steps",
        "output_template",
    }
    return {k: sketch[k] for k in allowed if k in sketch}
