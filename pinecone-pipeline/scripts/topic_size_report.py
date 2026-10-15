"""One-off / dev: aggregate chunk cache and source_data size by corpusTopic."""

from __future__ import annotations

import json
import os
from collections import defaultdict

from corpus_metadata import ROOT_TOPIC_SLUGS, derive_corpus_metadata


def _fmt_bytes(num_bytes: int) -> str:
    n = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024.0 or unit == "GB":
            if unit == "B":
                return f"{int(n)} B"
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{num_bytes} B"


def main() -> None:
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    chunk_dir = os.path.join(repo, "chunk_output")
    source_root = os.path.join(repo, "source_data")

    topic_chunks: dict[str, int] = defaultdict(int)
    topic_tokens: dict[str, int] = defaultdict(int)
    topic_docs: dict[str, set[str]] = defaultdict(set)
    topic_content_chars: dict[str, int] = defaultdict(int)

    for name in os.listdir(chunk_dir):
        if not name.endswith(".jsonl") or name.endswith(".embeddings.jsonl"):
            continue
        path = os.path.join(chunk_dir, name)
        with open(path, encoding="utf-8") as chunk_file:
            for line in chunk_file:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                rel = obj["sourceRelativePath"]
                meta = derive_corpus_metadata(rel)
                topic = meta["corpusTopic"]
                topic_chunks[topic] += 1
                tokens_val = obj["tokens"]
                topic_tokens[topic] += int(tokens_val) if tokens_val is not None else 0
                doc_id = obj["docId"]
                if doc_id:
                    topic_docs[topic].add(doc_id)
                content = obj["content"] if obj.get("content") is not None else ""
                topic_content_chars[topic] += len(content)

    topic_files: dict[str, int] = defaultdict(int)
    topic_bytes: dict[str, int] = defaultdict(int)

    if os.path.isdir(source_root):
        for dirpath, _dirnames, filenames in os.walk(source_root):
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                rel = os.path.relpath(fp, source_root).replace("\\", "/")
                meta = derive_corpus_metadata(rel)
                topic = meta["corpusTopic"]
                topic_files[topic] += 1
                topic_bytes[topic] += os.path.getsize(fp)

    expected = list(ROOT_TOPIC_SLUGS)

    print("Expected corpusTopic slugs (from SOURCE_DATA_ROOT_SEGMENTS):")
    for slug in expected:
        print(f"  - {slug}")
    print()

    chunk_topics = sorted(topic_chunks.keys())
    print("=== Cached chunks (chunk_output/*.jsonl, excluding *.embeddings.jsonl) ===")
    header = f"{'corpusTopic':<52} {'chunks':>8} {'docs':>6} {'tokens':>10} {'content_MiB':>12}"
    print(header)
    total_c = total_t = 0
    for topic in chunk_topics:
        doc_count = len(topic_docs[topic])
        chunk_count = topic_chunks[topic]
        token_sum = topic_tokens[topic]
        mib = topic_content_chars[topic] / (1024 * 1024)
        total_c += chunk_count
        total_t += token_sum
        print(f"{topic:<52} {chunk_count:>8} {doc_count:>6} {token_sum:>10} {mib:>11.2f} MiB")
    print(f"{'TOTAL':<52} {total_c:>8} {'':>6} {total_t:>10}")
    print()

    print("=== source_data files (by first path segment -> corpusTopic) ===")
    sd_topics = sorted(topic_files.keys())
    print(f"{'corpusTopic':<52} {'files':>8} {'size':>14}")
    total_f = total_b = 0
    for topic in sd_topics:
        file_count = topic_files[topic]
        byte_sum = topic_bytes[topic]
        total_f += file_count
        total_b += byte_sum
        print(f"{topic:<52} {file_count:>8} {_fmt_bytes(byte_sum):>14}")
    print(f"{'TOTAL':<52} {total_f:>8} {_fmt_bytes(total_b):>14}")
    print()

    missing_chunks = [slug for slug in expected if slug not in topic_chunks]
    if missing_chunks:
        print("Expected topics with NO chunks in cache (0 rows in first table):")
        for slug in missing_chunks:
            print(f"  - {slug}")
    extra = sorted(set(topic_chunks) - set(expected) - {"unknown_root"})
    if extra:
        print("Topics in cache not in ROOT_TOPIC_SLUGS:", extra)
    if "unknown_root" in topic_chunks:
        print(f"unknown_root chunks: {topic_chunks['unknown_root']}")


if __name__ == "__main__":
    main()
