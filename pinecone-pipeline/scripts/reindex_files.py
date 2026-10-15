#!/usr/bin/env python3
"""Re-chunk and optionally upsert specific corpus files (without full corpus scan)."""

from __future__ import annotations

import argparse
import os
import sys
import traceback

from dotenv import load_dotenv

_pipeline_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ragstone_root = os.path.dirname(_pipeline_dir)
if _pipeline_dir not in sys.path:
    sys.path.insert(0, _pipeline_dir)

from cli import (  # noqa: E402
    get_cache_path_for_file,
    is_cache_fresh,
    load_cached_objects,
)
from document_parser import (  # noqa: E402
    build_objects_for_file,
    build_output_path_for_objects,
    write_objects_to_jsonl,
)


def _load_dotenv() -> None:
    dotenv_path = os.environ.get("DOTENV_PATH", "").strip()
    if dotenv_path:
        load_dotenv(dotenv_path)
    elif os.path.isfile(os.path.join(_ragstone_root, ".env")):
        load_dotenv(os.path.join(_ragstone_root, ".env"))
    else:
        load_dotenv(os.path.join(_pipeline_dir, ".env"))


def _parse_namespace_list(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def _namespaces_from_env() -> list[str]:
    namespaces: list[str] = []
    for env_key in ("PINECONE_NAMESPACE_DEV", "PINECONE_NAMESPACE_PROD"):
        ns = os.environ.get(env_key, "").strip()
        if ns and ns not in namespaces:
            namespaces.append(ns)
    if not namespaces:
        namespaces = _parse_namespace_list(os.environ.get("PINECONE_NAMESPACES", ""))
    if not namespaces:
        namespaces = ["v3", "production"]
    return namespaces


def reindex_file(
    file_path: str,
    *,
    docs_dir: str,
    chunk_output_dir: str,
    send_to_pinecone: bool,
    generate_summaries: bool,
    cache_embeddings_to_disk: bool,
    sharepoint_base_url: str | None,
    pinecone_index: str,
    pinecone_namespaces: list[str],
    force: bool,
) -> int:
    if not os.path.isfile(file_path):
        print(f"File not found: {file_path}", file=sys.stderr)
        return 1

    os.makedirs(chunk_output_dir, exist_ok=True)
    cache_path = get_cache_path_for_file(file_path, chunk_output_dir)
    if force:
        for stale in (cache_path, cache_path.replace(".jsonl", ".embeddings.jsonl")):
            if os.path.isfile(stale):
                os.remove(stale)
                print(f"Removed cache: {stale}")

    objects: list[dict] = []
    if not force and is_cache_fresh(file_path, cache_path):
        objects = load_cached_objects(cache_path)
        print(f"Loaded {len(objects)} chunks from cache")
    if not objects:
        print(f"Parsing: {file_path}")
        objects = build_objects_for_file(
            file_path,
            sharepoint_base_url=sharepoint_base_url,
            docs_root=docs_dir,
        )
        if objects:
            out_path = build_output_path_for_objects(file_path, objects)
            write_objects_to_jsonl(out_path, objects)
            print(f"Wrote {len(objects)} chunks -> {out_path}")

    if not objects:
        print("No chunks produced", file=sys.stderr)
        return 1

    if not send_to_pinecone:
        return 0

    objects_to_upsert = list(objects)
    if generate_summaries:
        from summary_spans import build_summary_index_objects

        summary_objs = build_summary_index_objects(objects)
        objects_to_upsert = list(objects) + summary_objs
        print(f"Built {len(summary_objs)} summary span vectors")

    from pinecone_io import embedding_sidecar_path, upsert_objects_to_namespaces

    emb_cache_path = (
        embedding_sidecar_path(cache_path) if cache_embeddings_to_disk else None
    )
    stats = upsert_objects_to_namespaces(
        index_name=pinecone_index,
        objects=objects_to_upsert,
        namespaces=pinecone_namespaces,
        batch_size=100,
        embedding_cache_path=emb_cache_path,
    )
    print(
        f"Upserted {stats.pinecone_upsert_rows} vector writes; "
        f"OpenAI embeds: {stats.openai_embedding_api_calls}, "
        f"cache hits: {stats.embedding_cache_hits}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", help="Absolute or docs_dir-relative file paths")
    parser.add_argument("--force", action="store_true", help="Drop JSONL/embeddings cache first")
    args = parser.parse_args()

    _load_dotenv()
    pipeline_dir = _pipeline_dir
    docs_dir = os.environ.get("DOCS_DIR", os.path.join(pipeline_dir, "source_data"))
    chunk_output_dir = os.environ.get(
        "CHUNK_OUTPUT_DIR", os.path.join(pipeline_dir, "chunk_output")
    )
    send_to_pinecone = os.environ.get("SEND_TO_PINECONE", "0").strip() not in (
        "",
        "0",
        "false",
        "no",
        "off",
    )
    gen_raw = os.environ.get("GENERATE_SUMMARIES", "").strip().lower()
    if gen_raw in ("0", "false", "no", "off"):
        generate_summaries = False
    elif gen_raw in ("1", "true", "yes", "on"):
        generate_summaries = True
    else:
        generate_summaries = send_to_pinecone
    cache_embeddings_to_disk = os.environ.get("CACHE_EMBEDDINGS_TO_DISK", "1").strip().lower() not in (
        "",
        "0",
        "false",
        "no",
        "off",
    )
    pinecone_index = (
        os.environ.get("PINECONE_INDEX_NAME", "").strip()
        or os.environ.get("PINECONE_INDEX", "").strip()
        or "text-embedding-3-small"
    )
    sharepoint_base_url = os.environ.get("SHAREPOINT_BASE_URL", "").strip() or None
    pinecone_namespaces = _namespaces_from_env()

    exit_code = 0
    for raw_path in args.files:
        file_path = raw_path if os.path.isabs(raw_path) else os.path.join(docs_dir, raw_path)
        try:
            result = reindex_file(
                file_path,
                docs_dir=docs_dir,
                chunk_output_dir=chunk_output_dir,
                send_to_pinecone=send_to_pinecone,
                generate_summaries=generate_summaries,
                cache_embeddings_to_disk=cache_embeddings_to_disk,
                sharepoint_base_url=sharepoint_base_url,
                pinecone_index=pinecone_index,
                pinecone_namespaces=pinecone_namespaces,
                force=args.force,
            )
            exit_code = max(exit_code, result)
        except Exception as exc:
            print(f"Error: {file_path}: {exc}", file=sys.stderr)
            traceback.print_exc()
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
