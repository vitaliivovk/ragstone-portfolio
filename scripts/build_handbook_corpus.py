#!/usr/bin/env python3
"""
Build ``teams-bot/rag/handbook_corpus.json`` from Pinecone pipeline chunk JSONL.

Deduplicates rolling overlap between consecutive chunks (same scheme as token audit).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHUNK_DIR = REPO_ROOT / "pinecone-pipeline" / "chunk_output"
OUT_PATH = REPO_ROOT / "teams-bot" / "rag" / "handbook_corpus.json"

INSTR_PREFIX = "Instrukcja_dla_nowego_pracownika_2025"


def _dedupe_rows(path: Path) -> str:
    rows: list[tuple[int, int, str]] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            rows.append(
                (
                    int(record["blockStartIndex"]),
                    int(record["blockEndIndex"]),
                    str(record["content"]),
                )
            )
    rows.sort(key=lambda row: row[0])
    parts: list[str] = []
    for _start, _end, content in rows:
        if not parts:
            parts.append(content)
            continue
        previous = parts[-1]
        best_overlap = 0
        upper = min(len(previous), len(content))
        for overlap_len in range(upper, 19, -1):
            if previous.endswith(content[:overlap_len]):
                best_overlap = overlap_len
                break
        parts.append(content[best_overlap:])
    return "".join(parts)


def _jsonl_source_ext(path: Path) -> str:
    with open(path, encoding="utf-8") as handle:
        first_line = handle.readline().strip()
    if not first_line:
        return ""
    record = json.loads(first_line)
    file_ext = record["fileExt"]
    if file_ext:
        return str(file_ext).lower()
    source_path = record["sourceRelativePath"]
    return Path(str(source_path)).suffix.lstrip(".").lower()


def _pick_jsonl(prefix: str) -> Path:
    matches = list(CHUNK_DIR.glob(f"{prefix}*.jsonl"))
    non_embedding = [path for path in matches if ".embeddings." not in path.name]
    candidates = non_embedding if non_embedding else matches
    if not candidates:
        raise FileNotFoundError(f"No chunk JSONL for prefix {prefix!r} under {CHUNK_DIR}")

    pdf_candidates = [path for path in candidates if _jsonl_source_ext(path) == "pdf"]
    pool = pdf_candidates if pdf_candidates else candidates
    return max(pool, key=lambda path: path.stat().st_mtime)


def main() -> int:
    if not CHUNK_DIR.is_dir():
        print(f"Chunk directory not found: {CHUNK_DIR}", file=sys.stderr)
        return 1
    instr_path = _pick_jsonl(INSTR_PREFIX)
    payload = {
        "instrukcja_dla_nowego_pracownika_2025": _dedupe_rows(instr_path),
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    print(f"Wrote {OUT_PATH} ({instr_path.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
