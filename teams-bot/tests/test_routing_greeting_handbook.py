"""Greeting heuristic, post-retrieve routing, and handbook-vs-RAG consistency."""

from __future__ import annotations

from langchain_core.messages import HumanMessage

from rag.graph import route_after_retrieve
from rag.nodes import is_short_greeting_or_acknowledgment


def test_typos_czescz_treated_as_greeting() -> None:
    assert is_short_greeting_or_acknowledgment("czescz")
    assert is_short_greeting_or_acknowledgment("  Czesc!  ")
    assert is_short_greeting_or_acknowledgment("cześć")


def test_normal_question_not_greeting() -> None:
    assert not is_short_greeting_or_acknowledgment(
        "jak wygląda weryfikacja najemców w CRM"
    )
    assert not is_short_greeting_or_acknowledgment("czy mogę użyć innego adresu email")


def test_route_after_retrieve_prefers_rag_when_context_present() -> None:
    state = {
        "context": "**Fragment 1**\n---\nbody\n---",
        "sources": [{"fileName": "x.pdf"}],
    }
    assert route_after_retrieve(state) == "respond_with_rag"


def test_route_after_retrieve_falls_back_when_empty() -> None:
    state = {"context": "", "sources": []}
    assert route_after_retrieve(state) == "respond_direct"


def test_route_after_retrieve_falls_back_on_whitespace_only_context() -> None:
    state = {"context": "   \n", "sources": []}
    assert route_after_retrieve(state) == "respond_direct"


def test_route_after_retrieve_requires_non_empty_sources() -> None:
    state = {"context": "some text", "sources": []}
    assert route_after_retrieve(state) == "respond_direct"


def test_route_after_retrieve_accepts_human_message_free_state() -> None:
    """``ChatState`` always has more keys; router only reads context + sources."""
    state = {
        "messages": [HumanMessage(content="x")],
        "context": "c",
        "sources": [{"fileName": "a"}],
    }
    assert route_after_retrieve(state) == "respond_with_rag"
