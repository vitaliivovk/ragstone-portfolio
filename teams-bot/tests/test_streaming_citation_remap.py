"""Tests for streaming-visible text helpers and bibliography row precompute in ``rag/citations.py``.

Live chunks use :func:`streaming_safe_answer_visible_text` (legacy tail hiding + safe
``[`` truncation). **Źródła** rows come from retrieval via
:func:`precompute_streaming_citation_map`; the model must not emit ``[Źródło N]``.
"""
from __future__ import annotations

from rag.citations import (
    _truncate_partial_citations_used_line,
    _truncate_unclosed_inline_bracket,
    format_citations_from_display_rows,
    precompute_streaming_citation_map,
    streaming_safe_answer_visible_text,
    streaming_safe_remapped_text,
)


def _src(file_name: str, page_number: int | None = None, chunk_index: int | None = None) -> dict:
    return {
        "fileName": file_name,
        "pageNumber": page_number,
        "chunkIndex": chunk_index,
    }


class TestPrecomputeStreamingCitationMap:
    def test_dedup_collapses_same_file_and_page(self) -> None:
        sources = [
            _src("X.pdf", 5, 0),
            _src("X.pdf", 5, 1),
            _src("Y.pptx", 1, 0),
        ]
        ctx_to_display, display_rows, max_display = precompute_streaming_citation_map(sources)
        assert ctx_to_display == {1: 1, 2: 1, 3: 2}
        assert max_display == 2
        assert display_rows[0]["fileName"] == "X.pdf"
        assert display_rows[1]["fileName"] == "Y.pptx"

    def test_different_pages_same_file_merge_to_one_row(self) -> None:
        sources = [_src("X.pdf", 5), _src("X.pdf", 6), _src("X.pdf", 7)]
        ctx_to_display, display_rows, max_display = precompute_streaming_citation_map(sources)
        assert ctx_to_display == {1: 1, 2: 1, 3: 1}
        assert max_display == 1
        assert display_rows[0]["_citationPages"] == [5, 6, 7]

    def test_no_page_chunks_collapse_per_file(self) -> None:
        sources = [
            _src("X.docx", None, 0),
            _src("X.docx", None, 1),
            _src("Y.docx", None, 0),
        ]
        ctx_to_display, _, max_display = precompute_streaming_citation_map(sources)
        assert ctx_to_display == {1: 1, 2: 1, 3: 2}
        assert max_display == 2

    def test_empty_sources(self) -> None:
        assert precompute_streaming_citation_map([]) == ({}, [], 0)

    def test_map_is_deterministic_in_retrieval_order(self) -> None:
        sources_a = [_src("X.pdf", 5), _src("Y.pptx", 1)]
        sources_b = [_src("Y.pptx", 1), _src("X.pdf", 5)]
        map_a, _, _ = precompute_streaming_citation_map(sources_a)
        map_b, _, _ = precompute_streaming_citation_map(sources_b)
        assert map_a == {1: 1, 2: 2}
        assert map_b == {1: 1, 2: 2}


class TestTruncateUnclosedInlineBracket:
    def test_no_brackets_unchanged(self) -> None:
        assert _truncate_unclosed_inline_bracket("plain text") == "plain text"

    def test_complete_bracket_unchanged(self) -> None:
        assert _truncate_unclosed_inline_bracket("text [Źródło 1]") == "text [Źródło 1]"

    def test_unclosed_bracket_at_tail_is_dropped(self) -> None:
        assert _truncate_unclosed_inline_bracket("text [Źródło") == "text "

    def test_unclosed_bracket_with_partial_digits_dropped(self) -> None:
        assert _truncate_unclosed_inline_bracket("text [Źródło 12") == "text "

    def test_complete_then_unclosed_keeps_complete(self) -> None:
        assert (
            _truncate_unclosed_inline_bracket("a [Źródło 1] b [Źródło")
            == "a [Źródło 1] b "
        )


class TestTruncatePartialCitationsUsedLine:
    def test_no_match_unchanged(self) -> None:
        assert (
            _truncate_partial_citations_used_line("regular paragraph text")
            == "regular paragraph text"
        )

    def test_partial_prefix_at_start_of_trailing_line_is_hidden(self) -> None:
        assert (
            _truncate_partial_citations_used_line("answer body\nCITAT")
            == "answer body"
        )

    def test_complete_machine_line_at_tail_is_hidden(self) -> None:
        assert (
            _truncate_partial_citations_used_line(
                "answer body\nCITATIONS_USED: 1, 3"
            )
            == "answer body"
        )

    def test_lowercase_partial_also_hidden(self) -> None:
        assert (
            _truncate_partial_citations_used_line("answer body\ncit")
            == "answer body"
        )


class TestStreamingSafeAnswerVisibleText:
    def test_wrapper_ignores_unused_map_args(self) -> None:
        assert streaming_safe_remapped_text("hello", {}, 0) == streaming_safe_answer_visible_text(
            "hello"
        )

    def test_unclosed_trailing_bracket_is_hidden(self) -> None:
        assert streaming_safe_answer_visible_text("a [Źródło 1] b [Źródło") == "a [Źródło 1] b "

    def test_partial_legacy_machine_line_is_hidden(self) -> None:
        assert streaming_safe_answer_visible_text("answer body\nCITATIONS_") == "answer body"

    def test_empty_buffer(self) -> None:
        assert streaming_safe_answer_visible_text("") == ""

    def test_monotonic_growth_during_token_streaming(self) -> None:
        partial_buffers = [
            "Pierwsze",
            "Pierwsze zdanie [",
            "Pierwsze zdanie [Źródło 1",
            "Pierwsze zdanie [Źródło 1].",
            "Pierwsze zdanie [Źródło 1]. Drugie [",
            "Pierwsze zdanie [Źródło 1]. Drugie [Źródło",
            "Pierwsze zdanie [Źródło 1]. Drugie [Źródło 2",
            "Pierwsze zdanie [Źródło 1]. Drugie [Źródło 2].",
            "Pierwsze zdanie [Źródło 1]. Drugie [Źródło 2]. Trzecie [Źródło 3].",
        ]
        last_ship = ""
        sequence: list[str] = []
        for buffer in partial_buffers:
            candidate = streaming_safe_answer_visible_text(buffer)
            if not candidate.startswith(last_ship):
                continue
            if len(candidate) > len(last_ship):
                sequence.append(candidate)
                last_ship = candidate
        assert sequence[-1] == (
            "Pierwsze zdanie [Źródło 1]. Drugie [Źródło 2]. Trzecie [Źródło 3]."
        )
        for i in range(1, len(sequence)):
            assert sequence[i].startswith(sequence[i - 1]), (
                f"chunk {i} ({sequence[i]!r}) does not extend chunk {i - 1} ({sequence[i - 1]!r})"
            )


class TestFormatCitationsFromDisplayRows:
    def test_renders_numbered_list_in_row_order(self) -> None:
        rows = [_src("X.pdf", 5), _src("Y.pptx", 1)]
        rendered = format_citations_from_display_rows(rows)
        lines = rendered.splitlines()
        assert lines[0].startswith("1. 📖 X.pdf")
        assert "str. 5" in lines[0]
        assert lines[1].startswith("2. 📖 Y.pptx")
        assert "str. 1" in lines[1]

    def test_merged_pages_sorted_in_label(self) -> None:
        row = _src("Instrukcja.pdf", 25)
        row["_citationPages"] = [25, 1, 10]
        rendered = format_citations_from_display_rows([row])
        assert "str. 1, 10, 25" in rendered

    def test_empty(self) -> None:
        assert format_citations_from_display_rows([]) == ""
