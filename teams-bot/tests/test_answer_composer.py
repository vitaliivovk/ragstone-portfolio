"""Tests for topic composer and clarification formatting."""

from __future__ import annotations

from rag.answer_composer import (
    build_topic_composer_block,
    format_clarification_response,
)


def test_build_deposit_topic_block() -> None:
    block = build_topic_composer_block("deposit_kaucja", numeric_answer_first=False)
    assert "kaucja" in block.lower()


def test_build_verification_topic_block() -> None:
    block = build_topic_composer_block("verification", numeric_answer_first=False)
    assert "weryfikac" in block.lower()


def test_build_early_termination_topic_block() -> None:
    block = build_topic_composer_block("early_termination", numeric_answer_first=False)
    assert "wcześniejsz" in block.lower() or "wczesniejsz" in block.lower()


def test_build_none_topic_empty() -> None:
    assert build_topic_composer_block("none", numeric_answer_first=False) == ""


def test_build_numeric_lead_rule_only() -> None:
    block = build_topic_composer_block("none", numeric_answer_first=True)
    assert "Zdanie otwierające" in block
    assert "kaucja" not in block.lower()


def test_build_deposit_with_numeric_lead() -> None:
    block = build_topic_composer_block("deposit_kaucja", numeric_answer_first=True)
    assert "Zdanie otwierające" in block
    assert "kaucja" in block.lower()


def test_format_clarification_response_max_two_bullets() -> None:
    text = format_clarification_response(["Pytanie A?", "Pytanie B?"])
    assert text.count("- ") == 2


def test_format_clarification_response_empty_fallback_is_generic() -> None:
    text = format_clarification_response([])
    low = text.lower()
    assert "doprecyzowania" in low
    assert "pierwszą umowę" not in low
    assert "przedłużenie" not in low
    assert "osoba prywatna" not in low
