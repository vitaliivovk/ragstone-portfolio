"""RAGStrategy includes ``direct_mode`` for the direct-response branch."""

from __future__ import annotations

from rag.optimizer import DirectMode, RAGStrategy
from rag.retrieval_filter import RetrievalScope


def test_rag_strategy_defaults_direct_mode_smalltalk() -> None:
    strategy = RAGStrategy(needs_rag=True, optimized_query="test")
    assert strategy.direct_mode == DirectMode.SMALLTALK


def test_rag_strategy_handbook_when_no_rag() -> None:
    strategy = RAGStrategy(
        needs_rag=False,
        optimized_query="jak dodać klienta do crm",
        direct_mode=DirectMode.HANDBOOK,
        retrieval_scopes=[RetrievalScope.ALL],
    )
    assert strategy.direct_mode == DirectMode.HANDBOOK
