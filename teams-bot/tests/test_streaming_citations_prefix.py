"""Tests for streaming visible text and legacy ``CITATIONS_USED:`` tail stripping."""

from rag.citations import (
    streaming_answer_visible_prefix,
    strip_trailing_citations_used_line,
)


def test_streaming_visible_prefix_holds_until_legacy_line_is_complete() -> None:
    """Incomplete ``CITATIONS_USE`` is not a full legacy line — stream the buffer as-is."""
    acc = "Odpowiedź.\nCITATIONS_USE"
    assert streaming_answer_visible_prefix(acc) == acc


def test_streaming_visible_prefix_strips_completed_legacy_line() -> None:
    acc = "Treść odpowiedzi.\nCITATIONS_USED: 1, 2"
    visible = streaming_answer_visible_prefix(acc)
    assert visible.rstrip() == "Treść odpowiedzi."


def test_strip_trailing_citations_used_line_matches_postprocess() -> None:
    acc = "Treść odpowiedzi.\nCITATIONS_USED: 1, 2"
    assert strip_trailing_citations_used_line(acc).rstrip() == "Treść odpowiedzi."


def test_streaming_visible_prefix_does_not_strip_polish_newline_capital_c() -> None:
    acc = "Opłać do 10 dnia miesiąca.\nCałkowita kwota wynosi 100 zł."
    assert streaming_answer_visible_prefix(acc) == acc


def test_streaming_visible_prefix_does_not_hide_paren_zrodlo_tail() -> None:
    acc = "Płatności przez BlueMedia lub przelew. (Źródło: [Źródło 3], [Źródło 4])"
    assert streaming_answer_visible_prefix(acc) == acc
