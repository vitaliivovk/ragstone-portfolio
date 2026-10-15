import os
import sys
import json
import traceback
from dataclasses import dataclass, field
from typing import List, Dict, Any

from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from document_parser import (
    list_supported_files,
    build_objects_for_file,
    build_output_path_for_objects,
    write_objects_to_jsonl,
    compute_doc_id,
)


def _parse_namespace_list(raw: str) -> List[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def load_cached_objects(jsonl_path: str) -> List[Dict[str, Any]]:
    """Load objects from a cached JSONL file."""
    if not os.path.exists(jsonl_path):
        return []
    
    objects = []
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    objects.append(json.loads(line))
    except Exception as exc:
        print(f"Error loading cached file {jsonl_path}: {exc}")
        return []
    
    return objects


def get_cache_path_for_file(file_path: str, chunk_output_dir: str) -> str:
    """Generate the expected cache path for a file without parsing it."""
    doc_id = compute_doc_id(file_path)
    base = os.path.splitext(os.path.basename(file_path))[0]
    safe_base = base.replace(" ", "_")
    name = f"{safe_base}.{doc_id}.jsonl"
    return os.path.join(chunk_output_dir, name)


def is_cache_fresh(file_path: str, cache_path: str) -> bool:
    """Check if cached results are newer than the source file."""
    if not os.path.exists(cache_path):
        return False
    
    try:
        file_mtime = os.path.getmtime(file_path)
        cache_mtime = os.path.getmtime(cache_path)
        return cache_mtime >= file_mtime
    except Exception:
        return False


@dataclass
class IndexRunSummary:
    """Aggregated stats for one `ragstone-index` run (printed at the end)."""

    files_discovered: int = 0
    files_with_chunks: int = 0
    total_chunks: int = 0
    cache_hits: int = 0
    jsonl_writes: int = 0
    skipped_empty: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    pinecone_enabled: bool = False
    pinecone_index: str = ""
    pinecone_namespaces: List[str] = field(default_factory=list)
    pinecone_vector_rows_upserted: int = 0
    openai_embedding_api_calls: int = 0
    embedding_cache_hits: int = 0
    embedding_disk_cache_enabled: bool = False
    total_summary_vectors: int = 0


def _print_run_summary(summary: IndexRunSummary) -> None:
    sep = "=" * 58
    print()
    print(sep)
    print("INDEX RUN SUMMARY")
    print(sep)
    print(f"Files discovered (supported extensions): {summary.files_discovered}")
    print(f"Files with at least one chunk:          {summary.files_with_chunks}")
    print(f"Total chunk records (this run):        {summary.total_chunks}")
    print(f"Summary routing vectors (this run):      {summary.total_summary_vectors}")
    print(f"Files loaded from cache (non-empty):    {summary.cache_hits}")
    print(f"Files with JSONL written this run:      {summary.jsonl_writes}")
    empty_n = len(summary.skipped_empty)
    print(f"Files with zero chunks (skipped):        {empty_n}")
    if summary.skipped_empty:
        for path in summary.skipped_empty:
            print(f"    • {path}")
    err_n = len(summary.errors)
    print(f"Errors (processing or Pinecone):         {err_n}")
    if summary.errors:
        for line in summary.errors:
            print(f"    • {line}")
    print("—" * 58)
    if summary.pinecone_enabled:
        print("Pinecone: ENABLED")
        print(f"  Index:      {summary.pinecone_index}")
        print(f"  Namespaces: {', '.join(summary.pinecone_namespaces)}")
        print(
            f"  Vector rows upserted (sum across namespaces): "
            f"{summary.pinecone_vector_rows_upserted}"
        )
        print(
            f"  OpenAI embedding API calls (new vectors): {summary.openai_embedding_api_calls}"
        )
        print(f"  Embedding cache hits (local reuse):       {summary.embedding_cache_hits}")
        print(
            f"  Local embedding cache files: "
            f"{'on (next to chunk JSONL)' if summary.embedding_disk_cache_enabled else 'off'}"
        )
    else:
        print("Pinecone: DISABLED (SEND_TO_PINECONE not truthy)")
        print("  Vector upserts: none")
        print("  OpenAI embeddings: none (embeddings run only when upserting)")
    print(sep)
    print()


def main() -> None:
    pipeline_dir = os.path.dirname(os.path.abspath(__file__))
    ragstone_root = os.path.dirname(pipeline_dir)
    dotenv_path = os.environ.get("DOTENV_PATH", "").strip()
    if dotenv_path:
        load_dotenv(dotenv_path)
    elif os.path.isfile(os.path.join(ragstone_root, ".env")):
        load_dotenv(os.path.join(ragstone_root, ".env"))
    else:
        load_dotenv(os.path.join(pipeline_dir, ".env"))

    docs_dir = os.environ.get(
        "DOCS_DIR",
        os.path.join(pipeline_dir, "source_data"),
    )
    chunk_output_dir = os.environ.get(
        "CHUNK_OUTPUT_DIR", 
        os.path.join(pipeline_dir, "chunk_output"),
    )
    send_to_pinecone = os.environ.get("SEND_TO_PINECONE", "0").strip() not in ("", "0", "false", "no", "off")
    gen_raw = os.environ.get("GENERATE_SUMMARIES", "").strip().lower()
    if gen_raw in ("0", "false", "no", "off"):
        generate_summaries = False
    elif gen_raw in ("1", "true", "yes", "on"):
        generate_summaries = True
    else:
        # Unset: align with Pinecone upserts — add routing vectors unless explicitly disabled.
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
    pinecone_namespaces: List[str] = []
    for env_key in ("PINECONE_NAMESPACE_DEV", "PINECONE_NAMESPACE_PROD"):
        ns = os.environ.get(env_key, "").strip()
        if ns and ns not in pinecone_namespaces:
            pinecone_namespaces.append(ns)
    if not pinecone_namespaces:
        pinecone_namespaces = _parse_namespace_list(os.environ.get("PINECONE_NAMESPACES", ""))
    if not pinecone_namespaces:
        pinecone_namespaces = ["v3", "production"]
    
    # SharePoint integration: base URL for document deep links
    # Example: https://tenant.sharepoint.com/sites/docs/Shared%20Documents
    sharepoint_base_url = os.environ.get("SHAREPOINT_BASE_URL", "").strip() or None
    if sharepoint_base_url:
        print(f"SharePoint integration enabled: {sharepoint_base_url}")
    if generate_summaries:
        if not send_to_pinecone:
            print("WARNING: GENERATE_SUMMARIES=1 but SEND_TO_PINECONE is off; summary LLM calls are skipped.")
        elif not gen_raw:
            print(
                "GENERATE_SUMMARIES unset + SEND_TO_PINECONE=1: span summaries ON "
                "(SUMMARY_MODEL chat per span). Set GENERATE_SUMMARIES=0 to skip."
            )
        else:
            print(
                "GENERATE_SUMMARIES enabled: OpenAI chat (SUMMARY_MODEL) per span + summary vectors in upsert batch."
            )

    paths = list_supported_files(docs_dir)
    if not paths:
        print(f"No supported files found in: {docs_dir}")
        return

    summary = IndexRunSummary(
        files_discovered=len(paths),
        pinecone_enabled=send_to_pinecone,
        pinecone_index=pinecone_index,
        pinecone_namespaces=list(pinecone_namespaces),
        embedding_disk_cache_enabled=send_to_pinecone and cache_embeddings_to_disk,
    )

    # Ensure chunk output directory exists
    os.makedirs(chunk_output_dir, exist_ok=True)

    for fpath in paths:
        objects: List[Dict[str, Any]] = []
        try:
            cache_path = get_cache_path_for_file(fpath, chunk_output_dir)

            if is_cache_fresh(fpath, cache_path):
                print(f"Loading cached results: {fpath}")
                objects = load_cached_objects(cache_path)
                if objects:
                    summary.cache_hits += 1
                    print(f"Loaded {len(objects)} chunks from cache -> {cache_path}")
                else:
                    print(f"Cache file empty or corrupted, reparsing: {fpath}")
                    objects = build_objects_for_file(
                        fpath,
                        sharepoint_base_url=sharepoint_base_url,
                        docs_root=docs_dir,
                    )
                    if objects:
                        out_path = build_output_path_for_objects(fpath, objects)
                        write_objects_to_jsonl(out_path, objects)
                        summary.jsonl_writes += 1
                        print(f"Wrote {len(objects)} chunks -> {out_path}")
            else:
                print(f"Parsing: {fpath}")
                objects = build_objects_for_file(
                    fpath,
                    sharepoint_base_url=sharepoint_base_url,
                    docs_root=docs_dir,
                )
                if objects:
                    out_path = build_output_path_for_objects(fpath, objects)
                    write_objects_to_jsonl(out_path, objects)
                    summary.jsonl_writes += 1
                    print(f"Wrote {len(objects)} chunks -> {out_path}")

        except Exception as exc:
            err_line = f"{fpath}: {exc}"
            summary.errors.append(err_line)
            print(f"Error processing file:\n{err_line}")
            traceback.print_exc()
            continue

        if not objects:
            summary.skipped_empty.append(fpath)
            continue

        summary.files_with_chunks += 1
        summary.total_chunks += len(objects)

        if send_to_pinecone:
            objects_to_upsert: List[Dict[str, Any]] = list(objects)
            if generate_summaries and objects:
                from summary_spans import build_summary_index_objects

                summary_objs = build_summary_index_objects(objects)
                summary.total_summary_vectors += len(summary_objs)
                objects_to_upsert = list(objects) + summary_objs
                print(f"  Built {len(summary_objs)} summary span vectors for upsert.")
            try:
                from pinecone_io import embedding_sidecar_path, upsert_objects_to_namespaces

                chunk_jsonl_path = get_cache_path_for_file(fpath, chunk_output_dir)
                emb_cache_path = (
                    embedding_sidecar_path(chunk_jsonl_path)
                    if cache_embeddings_to_disk
                    else None
                )

                stats = upsert_objects_to_namespaces(
                    index_name=pinecone_index,
                    objects=objects_to_upsert,
                    namespaces=pinecone_namespaces,
                    batch_size=100,
                    embedding_cache_path=emb_cache_path,
                )
                summary.pinecone_vector_rows_upserted += stats.pinecone_upsert_rows
                summary.openai_embedding_api_calls += stats.openai_embedding_api_calls
                summary.embedding_cache_hits += stats.embedding_cache_hits
                ns_display = ", ".join(pinecone_namespaces)
                print(
                    f"Upserted {stats.pinecone_upsert_rows} vector writes to Pinecone index '{pinecone_index}' "
                    f"(namespaces: {ns_display}); "
                    f"OpenAI embeds: {stats.openai_embedding_api_calls}, "
                    f"local cache hits: {stats.embedding_cache_hits}."
                )
            except Exception as exc:
                err_line = f"{fpath} (Pinecone upsert): {exc}"
                summary.errors.append(err_line)
                print(f"Error upserting to Pinecone:\n{err_line}")
                traceback.print_exc()

    _print_run_summary(summary)


if __name__ == "__main__":
    main()
