#!/usr/bin/env python3
"""
Run the Teams bot RAG graph locally using real OpenAI and Pinecone (no Functions, no Teams).

Prerequisites (env vars, same as local.settings / Azure Function App):
  OPENAI_API_KEY, PINECONE_API_KEY, PINECONE_INDEX_NAME (or PINECONE_INDEX), PINECONE_NAMESPACE

Optional:
  OPENAI_MODEL, OPENAI_EMBEDDING_MODEL
  AZURE_STORAGE_CONNECTION_STRING or AzureWebJobsStorage — conversation memory (omit to skip; history is disabled automatically when storage is unset)

By default, narrative output goes to stdout and the same content is appended to teams-bot/logs/local_rag_run.log;
Python logging (including RAG_TURN_AUDIT JSON) goes to stderr and the same log file.

Usage (from repo root or teams-bot):
  cd teams-bot
  python scripts/run_local_rag_tests.py
  python scripts/run_local_rag_tests.py --question "Twoje pytanie"
  python scripts/run_local_rag_tests.py --file my_questions.txt --limit 5
  python scripts/run_local_rag_tests.py --stream --verbose
  python scripts/run_local_rag_tests.py --no-log-file
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Callable, TextIO

from dotenv import load_dotenv

_TEAMS_BOT_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _TEAMS_BOT_ROOT.parent

if str(_TEAMS_BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(_TEAMS_BOT_ROOT))

load_dotenv(_REPO_ROOT / ".env")
load_dotenv(_TEAMS_BOT_ROOT / ".env")

from config import load_rag_stack_settings
from rag import RAGGraph, StreamingResult
from rag.teams_entry import astream_teams_entry
from rag.citations import format_citations, should_attach_source_block
from rag.request_audit import log_rag_turn_audit

AUDIT_LOGGER = logging.getLogger("ragstone.local_rag_tests.audit")
DEFAULT_LOG_PATH = _TEAMS_BOT_ROOT / "logs" / "local_rag_run.log"


class _FileOnlyWriter:
    """Append logging records to the session log (stderr uses a separate handler)."""

    def __init__(self, file_obj: TextIO):
        self._file = file_obj

    def write(self, stream: str) -> int:
        self._file.write(stream)
        self._file.flush()
        return len(stream)

    def flush(self) -> None:
        self._file.flush()


class RunSession:
    """Tee human-readable lines to stdout and optional log file; holds file handle for logging."""

    def __init__(self, log_path: Path | None):
        self.log_path = log_path
        self._file: TextIO | None = None
        self.emit: Callable[..., None]
        if log_path is None:
            self.emit = print
            return
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(log_path, "w", encoding="utf-8")

        def emit(*args, **kwargs) -> None:
            kwargs.pop("file", None)
            print(*args, **kwargs)
            print(*args, file=self._file, **kwargs)
            self._file.flush()

        self.emit = emit

    def log_file_writer(self) -> _FileOnlyWriter | None:
        if self._file is None:
            return None
        return _FileOnlyWriter(self._file)

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None


def _configure_logging(
    *,
    verbose: int,
    log_file_writer: _FileOnlyWriter | None,
) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    level = (
        logging.DEBUG
        if verbose >= 2
        else logging.INFO
        if verbose >= 1
        else logging.WARNING
    )
    root.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(fmt)
    root.addHandler(stderr_handler)
    if log_file_writer is not None:
        file_handler = logging.StreamHandler(log_file_writer)
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)

    AUDIT_LOGGER.setLevel(logging.INFO)
    AUDIT_LOGGER.propagate = False
    AUDIT_LOGGER.handlers.clear()
    for handler in root.handlers:
        AUDIT_LOGGER.addHandler(handler)


DEFAULT_QUESTIONS: list[str] = [
    "Cześć",
    (
        "Czym różnią się wzory „Przedłużenie najmu I” z oznaczeniami (N), (R) i (W) "
        "i kiedy który stosować?"
    ),
    "Co zawiera Załącznik 1 – OWU do umowy najmu I i jak wiąże się z umową główną?",
]


def _read_questions_file(path: Path, limit: int | None) -> list[str]:
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
        if limit is not None and len(lines) >= limit:
            break
    return lines


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local RAG harness (OpenAI + Pinecone), same graph as the Teams bot.",
    )
    parser.add_argument(
        "--question",
        "-q",
        action="append",
        dest="questions",
        default=None,
        help="Question text (repeat flag for multiple)",
    )
    parser.add_argument(
        "--file",
        "-f",
        type=Path,
        default=None,
        help="Plain text file: one question per line (# comments and blank lines ignored)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="With --file: max number of questions to run",
    )
    parser.add_argument(
        "--user-id",
        default="local-rag-test-user",
        help="Synthetic user id for memory isolation (Table Storage)",
    )
    parser.add_argument(
        "--user-name",
        default="local-harness",
        help="Synthetic display name for RAG_TURN_AUDIT",
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Do not load or persist conversation history",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Print LLM tokens as they arrive (stderr remains for logs)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Logging (-v INFO, -vv DEBUG)",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help=f"Session log path (default: {DEFAULT_LOG_PATH})",
    )
    parser.add_argument(
        "--no-log-file",
        action="store_true",
        help="Do not write a session log file (console only)",
    )
    return parser


async def _run_single_turn(
    graph: RAGGraph,
    question: str,
    *,
    user_id: str,
    include_history: bool,
    stream_to_stdout: bool,
) -> StreamingResult | None:
    result: StreamingResult | None = None
    async for item in astream_teams_entry(
        graph,
        user_message=question,
        user_id=user_id,
        conversation_id="",
        include_history=include_history,
        on_optimize=None,
        on_retrieve=None,
        on_retrieval_phase=None,
    ):
        if isinstance(item, StreamingResult):
            result = item
            continue
        if stream_to_stdout:
            print(item, end="", flush=True)
    if stream_to_stdout and result:
        print()
    return result


async def _async_main(args: argparse.Namespace, emit: Callable[..., None]) -> int:
    if args.questions is not None:
        questions = list(args.questions)
    elif args.file is not None:
        path = args.file.expanduser().resolve()
        if not path.is_file():
            print(f"File not found: {path}", file=sys.stderr)
            return 2
        questions = _read_questions_file(path, args.limit)
        if not questions:
            print("No questions found in file.", file=sys.stderr)
            return 2
    else:
        questions = DEFAULT_QUESTIONS

    openai_cfg, pinecone_cfg, storage_cfg = load_rag_stack_settings()
    graph = RAGGraph(
        openai_config=openai_cfg,
        pinecone_config=pinecone_cfg,
        storage=storage_cfg,
    )

    include_history = (not args.no_history) and storage_cfg.enabled

    for index, question in enumerate(questions, start=1):
        emit(f"\n{'=' * 60}\n[{index}/{len(questions)}] Q: {question}\n{'=' * 60}")
        started = time.perf_counter()
        meta = await _run_single_turn(
            graph,
            question,
            user_id=args.user_id,
            include_history=include_history,
            stream_to_stdout=args.stream,
        )
        elapsed = time.perf_counter() - started

        if meta is None:
            print("No StreamingResult produced.", file=sys.stderr)
            continue

        log_rag_turn_audit(
            AUDIT_LOGGER,
            teams_user_id=args.user_id,
            teams_user_name=args.user_name,
            user_message=question,
            assistant_response=meta.full_response,
            needs_rag=meta.needs_rag,
            optimized_query=meta.optimized_query,
            retrieval_scope=meta.retrieval_scope,
            search_focus=meta.search_focus,
            optimizer_reasoning=meta.optimizer_reasoning,
            pinecone_index=meta.pinecone_index,
            pinecone_namespace=meta.pinecone_namespace,
            pinecone_metadata_filter=meta.pinecone_metadata_filter,
            retrieval_k=meta.retrieval_k,
            retrieval_fallback_unfiltered=meta.retrieval_fallback_unfiltered,
            retrieved_sources=meta.sources,
            corpus_path_prefixes=meta.corpus_path_prefixes,
            answer_depth=meta.answer_depth,
            output_truncated_by_max_tokens=meta.output_truncated_by_max_tokens,
            reuse_previous_context=meta.reuse_previous_context,
            optimizer_saw_cached_retrieval=meta.optimizer_saw_cached_retrieval,
            cached_retrieval_age_min=meta.cached_retrieval_age_min,
            cached_retrieval_files=meta.cached_retrieval_files,
            conversation_id=meta.conversation_id,
            response_path=meta.response_path,
            clarification_needed=meta.clarification_needed,
            clarification_questions=meta.clarification_questions,
            answer_topic=meta.answer_topic,
            numeric_answer_first=meta.numeric_answer_first,
            context_chunk_ids=meta.context_chunk_ids,
        )

        if not args.stream:
            emit(meta.full_response)

        if meta.sources and (
            meta.attach_sources_block or should_attach_source_block(meta.full_response)
        ):
            block = format_citations(meta.sources)
            if block:
                emit(f"\n**Źródła:**\n{block}")

        emit(
            f"\n--- meta: needs_rag={meta.needs_rag} k={meta.retrieval_k} "
            f"scope={meta.retrieval_scope!r} prefixes={meta.corpus_path_prefixes!r} "
            f"index={meta.pinecone_index!r} "
            f"namespace={meta.pinecone_namespace!r} ({elapsed:.1f}s) ---"
        )
        if meta.optimizer_reasoning:
            emit(f"optimizer: {meta.optimizer_reasoning}")

    return 0


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    if args.no_log_file:
        log_path: Path | None = None
    elif args.log_file is not None:
        log_path = args.log_file.expanduser().resolve()
    else:
        log_path = DEFAULT_LOG_PATH

    session = RunSession(log_path)
    try:
        file_writer = session.log_file_writer()
        _configure_logging(verbose=args.verbose, log_file_writer=file_writer)
        if log_path is not None:
            AUDIT_LOGGER.info("Session log file: %s", log_path)

        raise SystemExit(asyncio.run(_async_main(args, emit=session.emit)))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130) from None
    finally:
        session.close()


if __name__ == "__main__":
    main()
