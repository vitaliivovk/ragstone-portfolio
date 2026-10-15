"""Tests for the cache-aware optimizer prompt block.

These exercise ``RAGOptimizer._format_last_retrieval`` (pure formatter, no LLM) so
they are deterministic and run in <50 ms.

Behaviour being verified:
1. Empty / missing cache → empty block (caller skips the section entirely).
2. Cache with previous query + sources → block contains query, file count, and
   the source paths (capped at ``_LAST_RETRIEVAL_FILES_LIMIT`` deduped).
3. ``timestamp`` is rendered as ``Wiek: N min temu`` when parsable.
4. Query truncation at ``_LAST_RETRIEVAL_QUERY_CHAR_LIMIT`` chars.
5. ``optimize`` ainvoke receives the cache block in the user prompt when a
   non-empty ``last_retrieval`` is passed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage

from rag.user_preferences import format_user_preferences_prompt_block

from rag.optimizer import (
    AnswerDepth,
    RAGOptimizer,
    RAGStrategy,
    ReusePreviousContext,
    _LAST_RETRIEVAL_FILES_LIMIT,
    _LAST_RETRIEVAL_QUERY_CHAR_LIMIT,
)
from rag.retrieval_filter import RetrievalScope


def test_empty_cache_returns_empty_block() -> None:
    assert RAGOptimizer._format_last_retrieval(None) == ""
    assert RAGOptimizer._format_last_retrieval({}) == ""
    assert (
        RAGOptimizer._format_last_retrieval({"sources": [], "optimized_query": ""})
        == ""
    )


def test_cache_with_query_and_sources_renders_full_block() -> None:
    cached = {
        "optimized_query": "jak wygląda weryfikacja najemców",
        "sources": [
            {"sourceRelativePath": "5_instrukcje/weryfikacja_najemcow.md"},
            {"sourceRelativePath": "1_najem_instytucjonalny/weryfikacja_manualna.md"},
            {"fileName": "owu_najemu.md"},
        ],
        "timestamp": "",
    }
    block = RAGOptimizer._format_last_retrieval(cached)
    assert "Wcześniejsze wyszukiwanie" in block
    assert "jak wygląda weryfikacja najemców" in block
    assert "Liczba pobranych fragmentów: 3" in block
    assert "5_instrukcje/weryfikacja_najemcow.md" in block
    assert "weryfikacja_manualna.md" in block
    assert "owu_najemu.md" in block  # falls back to fileName when no path


def test_duplicate_paths_are_deduplicated() -> None:
    cached = {
        "optimized_query": "x",
        "sources": [
            {"sourceRelativePath": "5_instrukcje/a.md"},
            {"sourceRelativePath": "5_instrukcje/a.md"},
            {"sourceRelativePath": "5_instrukcje/b.md"},
        ],
    }
    block = RAGOptimizer._format_last_retrieval(cached)
    assert block.count("5_instrukcje/a.md") == 1
    assert "5_instrukcje/b.md" in block


def test_files_capped_at_limit() -> None:
    sources = [
        {"sourceRelativePath": f"corpus/file_{i:02d}.md"}
        for i in range(_LAST_RETRIEVAL_FILES_LIMIT + 5)
    ]
    cached = {"optimized_query": "x", "sources": sources}
    block = RAGOptimizer._format_last_retrieval(cached)
    rendered = [
        line for line in block.splitlines() if line.strip().startswith("- corpus/")
    ]
    assert len(rendered) == _LAST_RETRIEVAL_FILES_LIMIT


def test_timestamp_renders_age_in_minutes() -> None:
    five_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
    cached = {
        "optimized_query": "x",
        "sources": [{"sourceRelativePath": "a/b.md"}],
        "timestamp": five_minutes_ago.isoformat(),
    }
    block = RAGOptimizer._format_last_retrieval(cached)
    assert "Wiek:" in block
    # Allow ±1 min for clock drift between datetime.now() and the test.
    assert any(f"Wiek: {n} min" in block for n in (4, 5, 6))


def test_invalid_timestamp_omits_age_line() -> None:
    cached = {
        "optimized_query": "x",
        "sources": [{"sourceRelativePath": "a/b.md"}],
        "timestamp": "not-a-real-iso-string",
    }
    block = RAGOptimizer._format_last_retrieval(cached)
    assert "Wiek:" not in block


def test_query_is_truncated_at_limit() -> None:
    long_query = "a" * (_LAST_RETRIEVAL_QUERY_CHAR_LIMIT + 200)
    cached = {
        "optimized_query": long_query,
        "sources": [{"sourceRelativePath": "a/b.md"}],
    }
    block = RAGOptimizer._format_last_retrieval(cached)
    # Block should contain at most LIMIT 'a's plus the ellipsis marker.
    assert "…" in block
    assert long_query not in block  # the full string is NOT echoed


@pytest.mark.asyncio
async def test_optimize_passes_cache_block_into_user_prompt() -> None:
    """The cache block must end up in the second message sent to the LLM."""
    optimizer = RAGOptimizer.__new__(RAGOptimizer)
    fake_strategy = RAGStrategy(
        needs_rag=True,
        optimized_query="weryfikacja manualna",
        num_documents=4,
        answer_depth=AnswerDepth.STANDARD,
        retrieval_scopes=[RetrievalScope.ALL],
        corpus_path_prefixes=None,
        corpus_file_name=None,
        corpus_source_relative_path=None,
        reuse_previous_context=ReusePreviousContext.AUGMENT,
    )
    optimizer.llm = type("FakeLLM", (), {"ainvoke": AsyncMock(return_value=fake_strategy)})()

    cached: dict[str, Any] = {
        "optimized_query": "jak wygląda weryfikacja najemców",
        "sources": [{"sourceRelativePath": "5_instrukcje/weryfikacja_manualna.md"}],
        "timestamp": "",
    }
    history = [HumanMessage(content="poprzednie pytanie")]
    result = await optimizer.optimize(
        "co to jest weryfikacja manualna?",
        history,
        last_retrieval=cached,
    )
    assert result.reuse_previous_context == ReusePreviousContext.AUGMENT
    optimizer.llm.ainvoke.assert_awaited_once()
    sent_messages = optimizer.llm.ainvoke.await_args.args[0]
    user_msg = sent_messages[-1].content
    assert "Wcześniejsze wyszukiwanie" in user_msg
    assert "5_instrukcje/weryfikacja_manualna.md" in user_msg
    assert "co to jest weryfikacja manualna?" in user_msg


@pytest.mark.asyncio
async def test_optimize_omits_cache_block_when_no_cache() -> None:
    optimizer = RAGOptimizer.__new__(RAGOptimizer)
    fake_strategy = RAGStrategy(
        needs_rag=True,
        optimized_query="x",
        num_documents=4,
        answer_depth=AnswerDepth.STANDARD,
        retrieval_scopes=[RetrievalScope.ALL],
        corpus_path_prefixes=None,
        corpus_file_name=None,
        corpus_source_relative_path=None,
        reuse_previous_context=ReusePreviousContext.NONE,
    )
    optimizer.llm = type("FakeLLM", (), {"ainvoke": AsyncMock(return_value=fake_strategy)})()

    await optimizer.optimize(
        "świeże pytanie",
        history=[],
        last_retrieval=None,
    )
    sent_messages = optimizer.llm.ainvoke.await_args.args[0]
    user_msg = sent_messages[-1].content
    assert "Wcześniejsze wyszukiwanie" not in user_msg


@pytest.mark.asyncio
async def test_optimize_includes_user_style_in_system_prompt() -> None:
    """Non-empty /style fragment is appended to the router system prompt."""
    optimizer = RAGOptimizer.__new__(RAGOptimizer)
    fake_strategy = RAGStrategy(
        needs_rag=True,
        optimized_query="x",
        num_documents=4,
        answer_depth=AnswerDepth.CONCISE,
        retrieval_scopes=[RetrievalScope.ALL],
        corpus_path_prefixes=None,
        corpus_file_name=None,
        corpus_source_relative_path=None,
        reuse_previous_context=ReusePreviousContext.NONE,
    )
    optimizer.llm = type("FakeLLM", (), {"ainvoke": AsyncMock(return_value=fake_strategy)})()

    prefs = format_user_preferences_prompt_block("only short sentences")
    await optimizer.optimize(
        "jak działa weryfikacja?",
        history=[],
        last_retrieval=None,
        user_preferences_block=prefs,
    )
    sent_messages = optimizer.llm.ainvoke.await_args.args[0]
    system_content = sent_messages[0].content
    assert "Preferencje stylu (/style)" in system_content
    assert "only short sentences" in system_content
