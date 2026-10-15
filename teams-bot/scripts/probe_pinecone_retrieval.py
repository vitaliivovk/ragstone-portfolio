#!/usr/bin/env python3
"""
Direct Pinecone similarity search (same embeddings + index/namespace as RAGGraph).

No LLM optimizer — use to judge whether the vector index returns sensible neighbors.

  cd teams-bot
  uv run --with-requirements requirements.txt python scripts/probe_pinecone_retrieval.py -f logs/corpus_qa_questions.txt -k 8

Requires: OPENAI_API_KEY, PINECONE_API_KEY, PINECONE_INDEX_NAME (or PINECONE_INDEX), PINECONE_NAMESPACE
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore

_TEAMS_BOT_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _TEAMS_BOT_ROOT.parent

if str(_TEAMS_BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(_TEAMS_BOT_ROOT))

load_dotenv(_REPO_ROOT / ".env")
load_dotenv(_TEAMS_BOT_ROOT / ".env")

from config import load_rag_stack_settings
from rag.retrieval_filter import RetrievalScope, pinecone_filter_for_scope


def _read_questions(path: Path) -> list[str]:
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def _snippet(text: str, max_len: int = 220) -> str:
    one_line = " ".join(text.split())
    if len(one_line) <= max_len:
        return one_line
    return one_line[: max_len - 3] + "..."


async def _probe(
    vectorstore: PineconeVectorStore,
    question: str,
    k: int,
    label: str,
    metadata_filter: dict | None,
) -> None:
    print(f"\n  --- {label} (k={k}, filter={metadata_filter!r}) ---")
    if metadata_filter is None:
        pairs = await vectorstore.asimilarity_search_with_score(question, k=k)
    else:
        pairs = await vectorstore.asimilarity_search_with_score(
            question, k=k, filter=metadata_filter
        )
    if not pairs:
        print("  (no results)")
        return
    for rank, (doc, score) in enumerate(pairs, start=1):
        meta = doc.metadata
        path_key = "sourceRelativePath"
        path_val = meta.get(path_key, meta.get("source", "?"))
        topic = meta.get("corpusTopic", "?")
        chunk_idx = meta.get("chunkIndex", "?")
        fname = meta.get("fileName", "?")
        print(f"  {rank}. score={score!r} corpusTopic={topic!r}")
        print(f"      chunkIndex={chunk_idx} file={fname}")
        print(f"      path={path_val}")
        print(f"      text={_snippet(doc.page_content)}")


async def _async_main() -> int:
    parser = argparse.ArgumentParser(description="Pinecone-only retrieval probe")
    parser.add_argument(
        "-f",
        "--file",
        type=Path,
        required=True,
        help="One question per line",
    )
    parser.add_argument("-k", type=int, default=8, help="Top-k per query")
    parser.add_argument(
        "--scoped",
        action="store_true",
        help="Also run fixed-scope queries (same scopes as corpus QA smoke test)",
    )
    args = parser.parse_args()

    path = args.file.expanduser().resolve()
    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        return 2

    questions = _read_questions(path)
    if not questions:
        print("No questions in file.", file=sys.stderr)
        return 2

    openai_cfg, pinecone_cfg, _storage = load_rag_stack_settings()
    embeddings = OpenAIEmbeddings(
        model=openai_cfg.embedding_model,
        openai_api_key=openai_cfg.api_key,
    )
    vectorstore = PineconeVectorStore(
        index_name=pinecone_cfg.index_name,
        embedding=embeddings,
        namespace=pinecone_cfg.namespace,
        pinecone_api_key=pinecone_cfg.api_key,
    )

    # Corpus QA order: rezerwacja, Najem F RODO, VAT/notarial, instrukcje, Najem I RODO, Northwind Club
    scoped_order: list[RetrievalScope] = [
        RetrievalScope.UMOWA_REZERWACYJNA,
        RetrievalScope.NAJEM_FIRMA,
        RetrievalScope.MIESZKANIA_Z_VATEM,
        RetrievalScope.INSTRUKCJE,
        RetrievalScope.NAJEM_INSTYTUCJONALNY,
        RetrievalScope.PROGRAM_NORTHWIND_CLUB,
        RetrievalScope.ZAKWATEROWANIE,
    ]

    print(
        f"index={pinecone_cfg.index_name!r} namespace={pinecone_cfg.namespace!r} "
        f"embedding={openai_cfg.embedding_model!r}"
    )
    print("Score semantics: Pinecone/LC return distance or similarity depending on metric; compare ranks, not absolute values.")

    for question_index, question in enumerate(questions):
        print(f"\n{'=' * 72}\nQ{question_index + 1}: {question}\n{'=' * 72}")
        await _probe(vectorstore, question, args.k, "unfiltered", None)

        if args.scoped and question_index < len(scoped_order):
            scope = scoped_order[question_index]
            flt = pinecone_filter_for_scope(scope)
            await _probe(
                vectorstore,
                question,
                min(args.k, 6),
                f"scoped {scope.value}",
                flt,
            )

    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_async_main()))


if __name__ == "__main__":
    main()
