"""Unit tests for conversation history limit helper."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from rag.memory import _apply_message_limit


def test_apply_message_limit_negative_one_returns_all() -> None:
    messages = [HumanMessage(content=str(index)) for index in range(5)]
    limited = _apply_message_limit(messages, -1)
    assert limited == messages


def test_apply_message_limit_zero_returns_empty() -> None:
    messages = [HumanMessage(content="x")]
    assert _apply_message_limit(messages, 0) == []


def test_apply_message_limit_truncates_tail() -> None:
    messages = [
        HumanMessage(content="a"),
        AIMessage(content="b"),
        HumanMessage(content="c"),
        AIMessage(content="d"),
    ]
    limited = _apply_message_limit(messages, 2)
    assert len(limited) == 2
    assert limited[0].content == "c"
    assert limited[1].content == "d"


def test_default_max_rag_context_constant() -> None:
    from rag import nodes

    assert nodes._DEFAULT_MAX_RAG_CONTEXT_CHARS == 48_000
