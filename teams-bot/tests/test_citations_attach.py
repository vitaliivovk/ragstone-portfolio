"""Tests for whether the Teams final message appends the **Źródła:** block."""

from rag.citations import (
    collapse_same_document_comma_citation_runs,
    indices_from_inline_source_brackets,
    should_attach_source_block,
    strip_inline_source_citation_markers,
)
from rag.nodes import postprocess_rag_answer_text


def test_strip_inline_source_citation_markers_removes_tags() -> None:
    text = "Alpha [Źródło 1]. Beta (Źródło 2) end."
    assert strip_inline_source_citation_markers(text) == "Alpha . Beta end."


def test_strip_inline_collapses_adjacent_duplicate_brackets() -> None:
    text = "Tak [Źródło 1][Źródło 1][Źródło 1]."
    assert strip_inline_source_citation_markers(text) == "Tak ."


def test_should_attach_when_inline_citations_even_if_partial_nie_znalazlem() -> None:
    answer = (
        "Terminy [Źródło 1]. Uwagi: numeru nie znalazłem ich w dostarczonych fragmentach.\n"
    )
    assert should_attach_source_block(answer) is True


def test_should_attach_false_for_global_no_info_phrase_without_inline_cites() -> None:
    answer = "Nie znalazłem tej informacji w dokumentacji.\n"
    assert should_attach_source_block(answer) is False


def test_postprocess_strips_legacy_citations_used_and_optional_inline_tags() -> None:
    """Trailing ``CITATIONS_USED:`` is ignored; **Źródła** come from retrieval."""
    sources = [
        {"fileName": "first.docx", "sourceRelativePath": "a/first.docx"},
        {"fileName": "second.docx", "sourceRelativePath": "b/second.docx"},
    ]
    raw = "Fakt z dokumentu A [Źródło 1].\nCITATIONS_USED: 2"
    display, picked, _citations_md, attach = postprocess_rag_answer_text(raw, sources)
    assert "[Źródło" not in display
    assert "CITATIONS_USED" not in display
    assert len(picked) == 2
    assert attach is True


def test_indices_from_inline_source_brackets_order_and_dedupe() -> None:
    text = "A [Źródło 2] b [Źródło 1] c [Źródło 2] d [Źródło 4]"
    assert indices_from_inline_source_brackets(text) == [2, 1, 4]


def test_collapse_same_document_comma_run_keeps_one_bracket() -> None:
    sources = [
        {"fileName": "umowa.docx", "sourceRelativePath": "1/umowa.docx"},
        {"fileName": "umowa.docx", "sourceRelativePath": "1/umowa.docx"},
        {"fileName": "umowa.docx", "sourceRelativePath": "1/umowa.docx"},
        {"fileName": "umowa.docx", "sourceRelativePath": "1/umowa.docx"},
    ]
    text = "Czynsz [Źródło 1], [Źródło 2], [Źródło 3], [Źródło 4]."
    cite_idx = [1, 2, 3, 4]
    new_text, new_idx = collapse_same_document_comma_citation_runs(text, cite_idx, sources)
    assert new_text == "Czynsz [Źródło 1]."
    assert new_idx == [1]


def test_collapse_skips_when_different_documents() -> None:
    sources = [
        {"fileName": "a.docx", "sourceRelativePath": "a.docx"},
        {"fileName": "b.docx", "sourceRelativePath": "b.docx"},
    ]
    text = "Mix [Źródło 1], [Źródło 2]."
    cite_idx = [1, 2]
    new_text, new_idx = collapse_same_document_comma_citation_runs(text, cite_idx, sources)
    assert new_text == text
    assert new_idx == cite_idx
