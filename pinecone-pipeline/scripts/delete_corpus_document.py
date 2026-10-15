"""Delete all Pinecone vectors for one indexed document (chunks + summary spans)."""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_pipeline_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ragstone_root = os.path.dirname(_pipeline_dir)
if _pipeline_dir not in sys.path:
    sys.path.insert(0, _pipeline_dir)

from pinecone_io import ensure_index, get_index, get_pinecone  # noqa: E402


def _load_dotenv() -> None:
    dotenv_path = os.environ.get("DOTENV_PATH", "").strip()
    if dotenv_path:
        load_dotenv(dotenv_path)
    elif os.path.isfile(os.path.join(_ragstone_root, ".env")):
        load_dotenv(os.path.join(_ragstone_root, ".env"))
    else:
        load_dotenv(os.path.join(_pipeline_dir, ".env"))


def _index_name_from_env() -> str:
    name = os.environ.get("PINECONE_INDEX_NAME", "").strip() or os.environ.get("PINECONE_INDEX", "").strip()
    if not name:
        raise RuntimeError("Set PINECONE_INDEX_NAME or PINECONE_INDEX")
    return name


def _namespaces_from_env() -> list[str]:
    namespaces: list[str] = []
    for env_key in ("PINECONE_NAMESPACE_DEV", "PINECONE_NAMESPACE_PROD"):
        ns = os.environ.get(env_key, "").strip()
        if ns and ns not in namespaces:
            namespaces.append(ns)
    if not namespaces:
        raw = os.environ.get("PINECONE_NAMESPACES", "").strip()
        if raw:
            namespaces = [part.strip() for part in raw.split(",") if part.strip()]
    if not namespaces:
        single = os.environ.get("PINECONE_NAMESPACE", "").strip()
        if single:
            namespaces = [single]
    if not namespaces:
        namespaces = ["v3", "production"]
    return namespaces


def delete_by_doc_id(index_name: str, namespace: str, doc_id: str) -> None:
    pc = get_pinecone()
    index = get_index(pc, index_name)
    ensure_index(pc, index_name)
    index.delete(filter={"docId": doc_id}, namespace=namespace)
    print(f"Deleted vectors with docId={doc_id!r} from index={index_name!r} namespace={namespace!r}")


def delete_by_source_path(index_name: str, namespace: str, source_relative_path: str) -> None:
    pc = get_pinecone()
    index = get_index(pc, index_name)
    ensure_index(pc, index_name)
    index.delete(
        filter={"sourceRelativePath": source_relative_path.replace("\\", "/")},
        namespace=namespace,
    )
    print(
        f"Deleted vectors with sourceRelativePath={source_relative_path!r} "
        f"from index={index_name!r} namespace={namespace!r}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--doc-id", help="Pinecone metadata docId (SHA1 of path + mtime)")
    group.add_argument(
        "--source-relative-path",
        help="Indexed sourceRelativePath under pinecone-pipeline/source_data/",
    )
    parser.add_argument(
        "--namespace",
        action="append",
        default=[],
        help="Pinecone namespace (repeatable; default: env DEV/PROD or v3,production)",
    )
    args = parser.parse_args()

    _load_dotenv()
    index_name = _index_name_from_env()
    namespaces = args.namespace or _namespaces_from_env()

    for namespace in namespaces:
        if args.doc_id:
            delete_by_doc_id(index_name, namespace, args.doc_id)
        else:
            delete_by_source_path(index_name, namespace, args.source_relative_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
