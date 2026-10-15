"""Agent prompts must not route to or cite the removed Procesy NW RENT deck."""

from __future__ import annotations

from rag.answer_composer import _TOPIC_BLOCKS
from rag.optimizer import RAG_OPTIMIZER_PROMPT
from rag.prompts import HANDBOOK_DIRECT_PROMPT, SYSTEM_PROMPT

_FORBIDDEN = (
    "Procesy_ NW RENT",
    "Procesy NW RENT 2025",
    "procesy_vd_rent",
    "CRM/Procesy",
    "z Procesów",
)


def test_optimizer_prompt_does_not_name_procesy_deck() -> None:
    lowered = RAG_OPTIMIZER_PROMPT.lower()
    for needle in _FORBIDDEN:
        assert needle.lower() not in lowered
    assert "instrukcji dla nowego pracownika 2025" in lowered


def test_handbook_direct_prompt_names_only_instrukcja() -> None:
    lowered = HANDBOOK_DIRECT_PROMPT.lower()
    for needle in _FORBIDDEN:
        assert needle.lower() not in lowered
    assert "instrukcja dla nowego pracownika 2025" in lowered


def test_system_prompt_example_cites_instrukcja_not_procesy() -> None:
    assert "Instrukcja dla nowego pracownika 2025.pdf" in SYSTEM_PROMPT
    for needle in _FORBIDDEN:
        assert needle not in SYSTEM_PROMPT


def test_answer_composer_blocks_do_not_name_procesy_deck() -> None:
    combined = "\n".join(_TOPIC_BLOCKS.values()).lower()
    for needle in _FORBIDDEN:
        assert needle.lower() not in combined
