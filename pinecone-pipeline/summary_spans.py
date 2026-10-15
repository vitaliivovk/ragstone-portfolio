"""
Group chunk JSONL objects into spans for summary routing vectors.

Spans respect ``sectionPath`` boundaries and a target token budget per span.
See pinecone-pipeline/README.md (Summary routing vectors).
"""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from pinecone_io import get_openai

# One httpx-backed client per worker thread — shared clients across threads can corrupt JSON bodies.
_openai_thread_local = threading.local()


def _openai_client_for_summaries() -> OpenAI:
    cached = getattr(_openai_thread_local, "client", None)
    if cached is None:
        cached = get_openai()
        _openai_thread_local.client = cached
    return cached


def _sanitize_chat_text(text: str) -> str:
    """Strip NUL / C0 controls that can break request JSON on some stacks."""
    if not isinstance(text, str):
        text = str(text)
    text = text.replace("\x00", " ")
    return "".join(
        char if (char in "\t\n\r" or ord(char) >= 32) else " " for char in text
    )


def _summary_parallelism() -> int:
    raw = os.environ.get("SUMMARY_PARALLELISM", "4").strip() or "4"
    try:
        workers = int(raw, 10)
    except ValueError:
        workers = 4
    return max(1, min(workers, 16))


def group_chunks_into_spans(
    chunks: List[Dict[str, Any]],
    *,
    max_span_tokens: int = 800,
) -> List[Dict[str, Any]]:
    """
    Partition ordered chunk objects into spans.

    Each span is a contiguous run of chunks with the same ``sectionPath`` until
    ``max_span_tokens`` (sum of chunk ``tokens`` fields) would be exceeded.
    """
    if not chunks:
        return []

    ordered = sorted(chunks, key=lambda c: int(c.get("chunkIndex") or 0))
    spans: List[Dict[str, Any]] = []
    current: List[Dict[str, Any]] = []
    current_tokens = 0
    current_path: Optional[str] = None

    def flush() -> None:
        nonlocal current, current_tokens, current_path
        if not current:
            return
        start = int(current[0]["chunkIndex"])
        end = int(current[-1]["chunkIndex"])
        text_parts = [c.get("content") or "" for c in current]
        combined = "\n\n".join(p for p in text_parts if p.strip())
        spans.append(
            {
                "chunkIndexStart": start,
                "chunkIndexEnd": end,
                "sectionPath": current_path,
                "chunks": list(current),
                "combinedText": combined,
                "tokenSum": current_tokens,
            }
        )
        current = []
        current_tokens = 0

    for ch in ordered:
        path = ch.get("sectionPath")
        tok = int(ch.get("tokens") or 0)
        if not current:
            current = [ch]
            current_tokens = tok
            current_path = path
            continue
        path_changed = path != current_path
        would_exceed = current_tokens + tok > max_span_tokens and len(current) > 0
        if path_changed or would_exceed:
            flush()
            current = [ch]
            current_tokens = tok
            current_path = path
        else:
            current.append(ch)
            current_tokens += tok
    flush()
    return spans


def summarize_span_text(combined_text: str, section_path: str, *, model: str) -> str:
    """Produce a short Polish abstract for embedding (2–4 sentences)."""
    client = _openai_client_for_summaries()
    body = _sanitize_chat_text(combined_text)[:12000]
    path_line = _sanitize_chat_text(section_path or "brak")
    sys_msg = (
        "Jesteś asystentem indeksującym dokumenty prawne Northwind Residences. "
        "Napisz krótkie streszczenie (2-4 zdania) po polsku, faktyczne, bez wymyślania. "
        "Uwzględnij typ dokumentu jeśli wynika z nagłówków."
    )
    user_msg = f"Sekcja (ścieżka): {path_line}\n\nTreść do streszczenia:\n{body}"
    # gpt-5* models reject non-default temperature; omit to use API default.
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_msg},
        ],
    )
    choice = resp.choices[0].message.content
    if not choice or not choice.strip():
        raise RuntimeError("Empty summary from OpenAI")
    return choice.strip()


def _summarize_one_span(span: Dict[str, Any], *, model: str) -> str:
    return summarize_span_text(
        span["combinedText"],
        str(span.get("sectionPath") or ""),
        model=model,
    )


def _summarize_spans_parallel(
    spans: List[Dict[str, Any]],
    *,
    model: str,
    parallelism: int,
) -> List[str]:
    span_count = len(spans)
    if span_count == 0:
        return []
    if span_count == 1 or parallelism <= 1:
        texts: List[str] = []
        for span_index, span in enumerate(spans):
            print(f"  Summary {span_index + 1}/{span_count} (chat)...", flush=True)
            texts.append(_summarize_one_span(span, model=model))
        return texts

    lock = threading.Lock()
    completed = [0]
    results: List[Optional[str]] = [None] * span_count

    def run_span(span_index: int, span: Dict[str, Any]) -> Tuple[int, str]:
        text = _summarize_one_span(span, model=model)
        with lock:
            completed[0] += 1
            print(f"  Summary {completed[0]}/{span_count} (chat, parallel)...", flush=True)
        return span_index, text

    with ThreadPoolExecutor(max_workers=parallelism) as pool:
        futures = [
            pool.submit(run_span, span_index, span)
            for span_index, span in enumerate(spans)
        ]
        for fut in as_completed(futures):
            span_index, summary_text = fut.result()
            results[span_index] = summary_text

    out_texts: List[str] = []
    for idx in range(span_count):
        cell = results[idx]
        if cell is None:
            raise RuntimeError("Parallel summarization lost a result")
        out_texts.append(cell)
    return out_texts


def build_summary_index_objects(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build Pinecone-ready summary objects (metadata + ``content`` for embedding) for one file.

    Reads ``SUMMARY_MODEL`` from the environment (default ``gpt-5-nano``).
    """
    if not chunks:
        return []
    model = os.environ.get("SUMMARY_MODEL", "gpt-5-nano").strip() or "gpt-5-nano"
    doc_id = chunks[0]["docId"]
    spans = group_chunks_into_spans(chunks)
    parallelism = _summary_parallelism()
    print(
        f"  Summaries: {len(spans)} span(s), SUMMARY_PARALLELISM={parallelism} "
        f"(set env to 1 for strictly sequential).",
        flush=True,
    )
    summary_texts = _summarize_spans_parallel(spans, model=model, parallelism=parallelism)
    out: List[Dict[str, Any]] = []
    for span_i, span in enumerate(spans):
        summary_text = summary_texts[span_i]
        first = span["chunks"][0]
        stable_id = f"{doc_id}:summary:{span_i:04d}"
        out.append(
            {
                "stableId": stable_id,
                "summaries": True,
                "content": summary_text,
                "spanId": f"{doc_id}:span:{span_i}",
                "docId": doc_id,
                "chunkIndexStart": span["chunkIndexStart"],
                "chunkIndexEnd": span["chunkIndexEnd"],
                "sectionPath": span.get("sectionPath"),
                "sectionTitle": first.get("sectionTitle"),
                "fileName": first.get("fileName"),
                "sourceRelativePath": first.get("sourceRelativePath"),
                "language": first.get("language", "pl"),
                "lastModified": first.get("lastModified"),
                "mimeType": first.get("mimeType"),
                "fileExt": first.get("fileExt"),
                "sharepointUrl": first.get("sharepointUrl"),
                "tokens": len(summary_text) // 4,
            }
        )
    return out
