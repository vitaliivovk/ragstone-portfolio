"""Optimizer history snippets must expose enough assistant text for repeat routing."""

from langchain_core.messages import AIMessage, HumanMessage

from rag.optimizer import RAGOptimizer


def test_format_history_keeps_long_assistant_turn() -> None:
    optimizer = RAGOptimizer.__new__(RAGOptimizer)
    long_assistant = "A" * 5000
    messages = [
        HumanMessage(content="Client wrote in English about the flat."),
        AIMessage(content=long_assistant),
    ]
    history_text = RAGOptimizer._format_history(optimizer, messages, max_messages=6)
    assert "AAAA" in history_text
    assert history_text.endswith("...")
    assert len(history_text) > 2000
