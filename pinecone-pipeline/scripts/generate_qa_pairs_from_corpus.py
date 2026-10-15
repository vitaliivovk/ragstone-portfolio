#!/usr/bin/env python3
"""
Sample files from distinct top-level folders under source_data/ (one file per folder) and
parse with the same stack as indexing (`build_objects_for_file`). **By default** this writes
a Markdown bundle for **Cursor agents** to read and fill in (question / answer / reference) —
no OpenAI API key.

Optional `--fill-with-openai` calls the OpenAI API (requires OPENAI_API_KEY).

Default out: pinecone-pipeline/agent_exports/corpus_qa_for_cursor.md (gitignored).

Examples:
  cd pinecone-pipeline
  uv run python scripts/generate_qa_pairs_from_corpus.py --seed 42
  uv run python scripts/generate_qa_pairs_from_corpus.py --format json --out agent_exports/bundle.json
  uv run python scripts/generate_qa_pairs_from_corpus.py --fill-with-openai --out agent_exports/filled.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv

_PIPELINE_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_EXPORT = _PIPELINE_ROOT / "agent_exports" / "corpus_qa_for_cursor.md"

if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

load_dotenv(_PIPELINE_ROOT.parent / ".env")
load_dotenv(_PIPELINE_ROOT / ".env")

from document_parser.chunking import count_tokens
from document_parser.core import (
    DOCS_DIR,
    build_objects_for_file,
    list_supported_files,
)


def _topic_key(file_path: str, docs_root: str) -> str:
    relative = os.path.relpath(file_path, docs_root)
    first = relative.split(os.sep)[0]
    return first


def _files_by_topic(paths: List[str], docs_root: str) -> Dict[str, List[str]]:
    buckets: Dict[str, List[str]] = defaultdict(list)
    for path in paths:
        buckets[_topic_key(path, docs_root)].append(path)
    for topic_files in buckets.values():
        topic_files.sort()
    return dict(buckets)


def _pick_files(
    buckets: Dict[str, List[str]],
    count: int,
    rng: random.Random,
) -> List[str]:
    topics = list(buckets.keys())
    if len(topics) < count:
        raise SystemExit(
            f"Need {count} distinct top-level folders under source_data; "
            f"found only {len(topics)}: {topics!r}"
        )
    rng.shuffle(topics)
    chosen_topics = topics[:count]
    out: List[str] = []
    for topic in chosen_topics:
        files_in_topic = buckets[topic]
        out.append(rng.choice(files_in_topic))
    return out


def _chunks_to_context(
    chunks: List[Dict[str, Any]], max_tokens: int
) -> Tuple[str, int, int]:
    """Return (markdown_body, tokens_used, chunks_included_count). max_tokens 0 = no limit."""
    parts: List[str] = []
    used = 0
    included = 0
    for ch in chunks:
        body = ch.get("content") or ""
        if not body.strip():
            continue
        label = ch.get("chunkIndex", 0)
        block = f"#### chunkIndex={label}\n\n{body}\n\n"
        if max_tokens <= 0:
            parts.append(block)
            used += count_tokens(block)
            included += 1
            continue
        block_tokens = count_tokens(block)
        if used + block_tokens > max_tokens:
            break
        parts.append(block)
        used += block_tokens
        included += 1
    return "".join(parts), used, included


def _call_openai(
    *,
    model: str,
    source_relative_path: str,
    file_name: str,
    context: str,
) -> Dict[str, Any]:
    from openai import OpenAI

    api_key = os.environ["OPENAI_API_KEY"]
    client = OpenAI(api_key=api_key)
    system = (
        "Jesteś asystentem do oceny korpusów RAG. Dostajesz fragmenty tekstu z jednego pliku "
        "(jak w indeksie: chunkIndex + treść). Wygeneruj TYLKO poprawny JSON wg schematu z promptu."
    )
    user = f"""Plik (nazwa): {file_name}
Ścieżka względna w korpusie (sourceRelativePath): {source_relative_path}

Treść fragmentów (chunkIndex odpowiada polu chunkIndex w metadanych indeksu):
{context}

Zadanie:
1. Zaproponuj **jedno** konkretne pytanie po polsku, na które da się odpowiedzieć WYŁĄCZNIE na podstawie powyższego tekstu (np. pytanie pracownika / najemcy o treści dokumentu).
2. Podaj **odpowiedź** po polsku, ściśle opartą na tekście (bez wiedzy zewnętrznej).
3. W polu **reference** wskaż:
   - source_relative_path: dokładnie jak wyżej
   - chunk_indices: lista indeksów chunków (liczby całkowite), z których wynika odpowiedź
   - rationale: jedno zdanie po polsku, co w tych fragmentach uzasadnia odpowiedź

Zwróć JSON:
{{
  "question": "...",
  "answer": "...",
  "reference": {{
    "source_relative_path": "...",
    "chunk_indices": [0, 1],
    "rationale": "..."
  }}
}}
"""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    raw = response.choices[0].message.content
    if not raw:
        raise RuntimeError("Empty model response")
    return json.loads(raw)


def _build_markdown(
    *,
    docs_root: str,
    seed: int | None,
    max_context_tokens: int,
    records: List[Dict[str, Any]],
) -> str:
    lines: List[str] = [
        "# Corpus Q&A — pack for Cursor agent",
        "",
        "This file was generated by `pinecone-pipeline/scripts/generate_qa_pairs_from_corpus.py`.",
        "Chunks use the **same parser and merge logic** as Pinecone indexing (`build_objects_for_file`).",
        "",
        "## Your task (no API key required)",
        "",
        "For **each document section** below:",
        "",
        "1. Read the indexed chunks.",
        "2. Propose **one** concrete question in Polish that is answerable **only** from that text.",
        "3. Write the **answer** in Polish, grounded strictly in those chunks.",
        "4. Fill **Reference**: `chunk_indices` you used, and a one-sentence **rationale**.",
        "",
        f"- Corpus root: `{docs_root}`",
        f"- RNG seed: `{seed}`",
        f"- Chunk excerpt token budget per file: `{max_context_tokens}` (`0` = include all chunks that have text).",
        f"- Generated at (UTC): `{datetime.now(timezone.utc).isoformat()}`",
        "",
        "---",
        "",
    ]
    for index, rec in enumerate(records, start=1):
        lines.append(f"## Document {index}: {rec['topic_folder']}")
        lines.append("")
        lines.append(f"- **sourceRelativePath:** `{rec['source_relative_path']}`")
        lines.append(f"- **fileName:** `{rec['file_name']}`")
        lines.append(f"- **Absolute path:** `{rec['file_path']}`")
        lines.append(f"- **Chunks in index:** {rec['chunk_count_indexed']}")
        lines.append(f"- **Chunks included below:** {rec['chunks_included']}")
        lines.append(f"- **Approx. tokens in excerpt:** {rec['context_tokens']}")
        lines.append("")
        if rec.get("error"):
            lines.append(f"**Error:** `{rec['error']}`")
            lines.append("")
            continue
        lines.append("### Indexed chunks (excerpt)")
        lines.append("")
        lines.append(rec["chunk_excerpt_markdown"])
        lines.append("")
        lines.append("### Agent — fill in")
        lines.append("")
        lines.append("| Field | Your answer |")
        lines.append("| --- | --- |")
        lines.append("| Question (PL) | |")
        lines.append("| Answer (PL) | |")
        lines.append("| chunk_indices (e.g. 0, 2) | |")
        lines.append("| Rationale (one sentence, PL) | |")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export corpus chunks for Cursor agents (default) or optionally fill with OpenAI.",
    )
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=Path(DOCS_DIR),
        help="Corpus root (default: pipeline source_data)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Files to sample (one per top-level folder). Default: min(8, number of folders).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="RNG seed for reproducible file picks",
    )
    parser.add_argument(
        "--max-context-tokens",
        type=int,
        default=24_000,
        help="Max tokens of chunk text per file in export (0 = no limit).",
    )
    parser.add_argument(
        "--fill-with-openai",
        action="store_true",
        help="After export data is built, call OpenAI (requires OPENAI_API_KEY). Implies --format json.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        help="With --fill-with-openai: chat model",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Export format (default markdown for agents).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=f"Output path (default: {_DEFAULT_EXPORT})",
    )
    args = parser.parse_args()

    fmt = "json" if args.fill_with_openai else args.format
    out_path = args.out
    if out_path is None:
        out_path = _DEFAULT_EXPORT if fmt == "markdown" else _DEFAULT_EXPORT.with_suffix(".json")

    docs_root = str(args.docs_dir.resolve())
    if not os.path.isdir(docs_root):
        raise SystemExit(f"DOCS_DIR is not a directory: {docs_root}")

    if args.fill_with_openai and not os.environ.get("OPENAI_API_KEY", "").strip():
        raise SystemExit("--fill-with-openai requires OPENAI_API_KEY")

    rng = random.Random(args.seed)
    all_paths = list_supported_files(docs_root)
    if not all_paths:
        raise SystemExit(f"No supported files under {docs_root}")

    buckets = _files_by_topic(all_paths, docs_root)
    topic_count = len(buckets)
    count = args.count if args.count is not None else min(8, topic_count)
    if count < 1:
        raise SystemExit("No top-level topic folders with supported files.")
    if count > topic_count:
        raise SystemExit(
            f"--count={count} but only {topic_count} distinct top-level folders exist."
        )
    picked = _pick_files(buckets, count, rng)

    records: List[Dict[str, Any]] = []

    for abs_path in picked:
        topic = _topic_key(abs_path, docs_root)
        objects = build_objects_for_file(abs_path, docs_root=docs_root)
        if not objects:
            records.append(
                {
                    "topic_folder": topic,
                    "file_path": abs_path,
                    "source_relative_path": None,
                    "file_name": os.path.basename(abs_path),
                    "error": "no_chunks_after_parse",
                    "chunk_count_indexed": 0,
                    "chunks_included": 0,
                    "context_tokens": 0,
                    "chunk_excerpt_markdown": "",
                }
            )
            continue

        excerpt, ctx_tokens, n_included = _chunks_to_context(
            objects, args.max_context_tokens
        )
        if not excerpt.strip():
            records.append(
                {
                    "topic_folder": topic,
                    "file_path": abs_path,
                    "source_relative_path": objects[0]["sourceRelativePath"],
                    "file_name": objects[0]["fileName"],
                    "error": "empty_context",
                    "chunk_count_indexed": len(objects),
                    "chunks_included": 0,
                    "context_tokens": 0,
                    "chunk_excerpt_markdown": "",
                }
            )
            continue

        rel_path = objects[0]["sourceRelativePath"]
        file_name = objects[0]["fileName"]
        rec: Dict[str, Any] = {
            "topic_folder": topic,
            "file_path": abs_path,
            "source_relative_path": rel_path,
            "file_name": file_name,
            "error": None,
            "chunk_count_indexed": len(objects),
            "chunks_included": n_included,
            "context_tokens": ctx_tokens,
            "chunk_excerpt_markdown": excerpt,
        }

        if args.fill_with_openai:
            try:
                rec["qa"] = _call_openai(
                    model=args.model,
                    source_relative_path=rel_path,
                    file_name=file_name,
                    context=excerpt,
                )
            except Exception as exc:
                rec["qa"] = None
                rec["error"] = str(exc)

        records.append(rec)

    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "markdown":
        body = _build_markdown(
            docs_root=docs_root,
            seed=args.seed,
            max_context_tokens=args.max_context_tokens,
            records=records,
        )
        out_path.write_text(body, encoding="utf-8")
        print(f"Wrote Markdown for Cursor agents -> {out_path}", file=sys.stderr)
        return

    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote JSON -> {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
