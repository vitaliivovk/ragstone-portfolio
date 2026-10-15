"""Apply metadata from local chunk JSONL cache to Pinecone via update() (no re-embedding)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Allow `uv run python scripts/patch_pinecone_metadata.py` from pinecone-pipeline/
_pipeline_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _pipeline_dir not in sys.path:
    sys.path.insert(0, _pipeline_dir)

from pinecone_io import (  # noqa: E402
    build_metadata_from_object,
    ensure_index,
    get_index,
    get_pinecone,
    _stable_vector_id,
)


def _list_chunk_jsonl_paths(chunk_dir: str) -> List[str]:
    out: List[str] = []
    for name in sorted(os.listdir(chunk_dir)):
        if not name.endswith(".jsonl") or name.endswith(".embeddings.jsonl"):
            continue
        out.append(os.path.join(chunk_dir, name))
    return out


def _load_objects_from_jsonl(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _index_name_from_env() -> str:
    name = os.environ.get("PINECONE_INDEX_NAME", "").strip() or os.environ.get("PINECONE_INDEX", "").strip()
    if not name:
        raise RuntimeError("Set PINECONE_INDEX_NAME or PINECONE_INDEX")
    return name


def _update_job(
    args: Tuple[Any, str, str, Dict[str, Any]],
) -> Tuple[str, bool, str]:
    index, namespace, vid, meta = args
    try:
        index.update(id=vid, set_metadata=meta, namespace=namespace)
        return (vid, True, "")
    except Exception as exc:
        return (vid, False, str(exc))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--chunk-dir",
        default=os.path.join(_pipeline_dir, "chunk_output"),
        help="Directory with *.jsonl chunk caches (default: pinecone-pipeline/chunk_output)",
    )
    parser.add_argument("--namespace", default="v3", help="Pinecone namespace (default: v3)")
    parser.add_argument(
        "--workers",
        type=int,
        default=6,
        help="Parallel update threads (default: 6)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load cache and print counts only; no Pinecone calls",
    )
    args = parser.parse_args()

    repo_root = os.path.dirname(_pipeline_dir)
    load_dotenv()
    load_dotenv(os.path.join(_pipeline_dir, ".env"))
    load_dotenv(os.path.join(repo_root, ".env"))
    chunk_dir = os.path.abspath(args.chunk_dir)
    if not os.path.isdir(chunk_dir):
        print(f"chunk dir not found: {chunk_dir}", file=sys.stderr)
        return 1

    paths = _list_chunk_jsonl_paths(chunk_dir)
    if not paths:
        print(f"No chunk *.jsonl files in {chunk_dir}", file=sys.stderr)
        return 1

    jobs: List[Tuple[str, str, Dict[str, Any]]] = []
    for jsonl_path in paths:
        for obj in _load_objects_from_jsonl(jsonl_path):
            vid = _stable_vector_id(obj)
            meta = build_metadata_from_object(obj)
            jobs.append((vid, jsonl_path, meta))

    print(f"Chunk files: {len(paths)}")
    print(f"Vectors to patch (metadata update): {len(jobs)}")
    if args.dry_run:
        if jobs:
            sample_vid, sample_path, sample_meta = jobs[0][0], jobs[0][1], jobs[0][2]
            keys = sorted(sample_meta.keys())
            print(f"Dry-run sample id={sample_vid} file={os.path.basename(sample_path)} metadata_keys={keys}")
        return 0

    index_name = _index_name_from_env()
    pc = get_pinecone()
    ensure_index(pc, index_name)
    index = get_index(pc, index_name)

    namespace = args.namespace.strip() or "v3"
    worker_args: List[Tuple[Any, str, str, Dict[str, Any]]] = [
        (index, namespace, vid, meta) for vid, _path, meta in jobs
    ]

    ok = 0
    failed: List[Tuple[str, str]] = []
    t0 = time.perf_counter()
    max_workers = max(1, int(args.workers))

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_update_job, job_arg) for job_arg in worker_args]
        for n_done, fut in enumerate(as_completed(futures), start=1):
            vid, success, err = fut.result()
            if success:
                ok += 1
            else:
                failed.append((vid, err))
            if n_done % 200 == 0 or n_done == len(futures):
                elapsed = time.perf_counter() - t0
                print(f"Progress {n_done}/{len(futures)} ({elapsed:.1f}s)")

    elapsed = time.perf_counter() - t0
    print(f"Done: {ok} updated, {len(failed)} failed, {elapsed:.1f}s namespace={namespace!r} index={index_name!r}")
    if failed:
        for vid, err in failed[:20]:
            print(f"  FAIL {vid}: {err}", file=sys.stderr)
        if len(failed) > 20:
            print(f"  ... and {len(failed) - 20} more", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
