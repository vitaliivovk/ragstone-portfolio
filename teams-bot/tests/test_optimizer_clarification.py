"""Tests for clarification gate on RAGStrategy and optimize node."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage

from rag.optimizer import (
    AnswerDepth,
    RAGOptimizer,
    RAGStrategy,
    ReusePreviousContext,
)
from rag.retrieval_filter import RetrievalScope
from rag.nodes import RAGNodes


@pytest.mark.asyncio
async def test_optimize_clarification_skips_rag_and_caps_questions() -> None:
    nodes = RAGNodes.__new__(RAGNodes)
    nodes.optimizer = RAGOptimizer.__new__(RAGOptimizer)
    nodes.optimizer.optimize = AsyncMock(
        return_value=RAGStrategy(
            needs_rag=True,
            clarification_needed=True,
            clarification_questions=[
                "Czy chodzi o pierwszą umowę, czy przedłużenie?",
                "Czy najemca to osoba prywatna, czy firma?",
            ],
            optimized_query="warunki najmu",
            num_documents=6,
            answer_depth=AnswerDepth.STANDARD,
            retrieval_scopes=[RetrievalScope.ALL],
            reuse_previous_context=ReusePreviousContext.REUSE,
        )
    )

    state = {
        "messages": [HumanMessage(content="jakie warunki najmu?")],
        "user_preferences_block": "",
    }
    out = await nodes.optimize(state)

    assert out["clarification_needed"] is True
    assert out["needs_rag"] is False
    assert len(out["clarification_questions"]) == 2
    assert out["reuse_previous_context"] == ReusePreviousContext.NONE.value


@pytest.mark.asyncio
async def test_optimize_no_clarify_when_optimizer_sets_flag_without_questions() -> None:
    nodes = RAGNodes.__new__(RAGNodes)
    nodes.optimizer = RAGOptimizer.__new__(RAGOptimizer)
    nodes.optimizer.optimize = AsyncMock(
        return_value=RAGStrategy(
            needs_rag=False,
            clarification_needed=True,
            clarification_questions=[],
            optimized_query="proces zamiany mieszkania",
            num_documents=6,
            answer_depth=AnswerDepth.STANDARD,
            retrieval_scopes=[RetrievalScope.ALL],
        )
    )

    state = {
        "messages": [HumanMessage(content="opisz proces zamiany mieszkania")],
        "user_preferences_block": "",
    }
    out = await nodes.optimize(state)

    assert out["clarification_needed"] is False
    assert out["clarification_questions"] == []


@pytest.mark.asyncio
async def test_respond_clarify_formats_questions_without_llm() -> None:
    nodes = RAGNodes.__new__(RAGNodes)
    out = await nodes.respond_clarify(
        {
            "clarification_questions": [
                "Na jakim etapie zamiany lokalu jest najemca?",
            ],
        }
    )
    assert "doprecyzowania" in out["response"].lower()
    assert "etapie zamiany" in out["response"]
    assert out["citations"] == ""
    assert out["attach_sources_block"] is False


def test_rag_strategy_clarification_fields_default() -> None:
    strategy = RAGStrategy(needs_rag=True, optimized_query="test")
    assert strategy.clarification_needed is False
    assert strategy.clarification_questions == []
    assert strategy.answer_depth == AnswerDepth.CONCISE
