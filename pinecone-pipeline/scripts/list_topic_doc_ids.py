"""List docIds for a corpusTopic in a namespace (sample via filtered query)."""

from __future__ import annotations

import os
import sys

_pipeline_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _pipeline_dir not in sys.path:
    sys.path.insert(0, _pipeline_dir)

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(_pipeline_dir), ".env"))

from pinecone_io import MODEL_NAME, get_index, get_openai, get_pinecone


def doc_ids_for_topic(namespace: str, topic: str) -> dict[str, set[str]]:
    index_name = (
        os.environ.get("PINECONE_INDEX_NAME", "").strip()
        or os.environ.get("PINECONE_INDEX", "").strip()
        or "text-embedding-3-small"
    )
    index = get_index(get_pinecone(), index_name)
    emb = get_openai().embeddings.create(model=MODEL_NAME, input=[topic]).data[0].embedding
    res = index.query(
        vector=emb,
        top_k=10000,
        namespace=namespace,
        filter={"corpusTopic": {"$eq": topic}},
        include_metadata=True,
    )
    by_path: dict[str, set[str]] = {}
    doc_ids: set[str] = set()
    for match in res.matches:
        meta = match.metadata or {}
        doc_id = str(meta.get("docId", ""))
        path = str(meta.get("sourceRelativePath", ""))
        if doc_id:
            doc_ids.add(doc_id)
        if path and doc_id:
            by_path.setdefault(path, set()).add(doc_id)
    return {"doc_ids": doc_ids, "by_path": by_path, "match_count": len(res.matches)}


def main() -> int:
    topic = sys.argv[1] if len(sys.argv) > 1 else "zakwaterowanie"
    for namespace in ("v3", "production"):
        data = doc_ids_for_topic(namespace, topic)
        print(f"\n=== {namespace} topic={topic!r} matches={data['match_count']} docIds={len(data['doc_ids'])} ===")
        for path in sorted(data["by_path"]):
            ids = sorted(data["by_path"][path])
            print(f"  {path}")
            for doc_id in ids:
                print(f"    {doc_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
