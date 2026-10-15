"""Unit tests for summary span grouping (no OpenAI calls)."""

from summary_spans import group_chunks_into_spans


def _chunk(idx: int, path: str, tokens: int, content: str) -> dict:
    return {
        "docId": "doc1",
        "chunkIndex": idx,
        "sectionPath": path,
        "tokens": tokens,
        "content": content,
        "fileName": "f.pdf",
        "sourceRelativePath": "1/a.pdf",
    }


def test_empty_chunks():
    assert group_chunks_into_spans([]) == []


def test_single_section_merges_until_token_budget():
    chunks = [
        _chunk(0, "A", 400, "p1"),
        _chunk(1, "A", 400, "p2"),
        _chunk(2, "A", 400, "p3"),
    ]
    spans = group_chunks_into_spans(chunks, max_span_tokens=800)
    assert len(spans) == 2
    assert spans[0]["chunkIndexStart"] == 0 and spans[0]["chunkIndexEnd"] == 1
    assert spans[1]["chunkIndexStart"] == 2 and spans[1]["chunkIndexEnd"] == 2


def test_section_path_boundary_starts_new_span():
    chunks = [
        _chunk(0, "Intro", 100, "a"),
        _chunk(1, "Body", 100, "b"),
    ]
    spans = group_chunks_into_spans(chunks, max_span_tokens=900)
    assert len(spans) == 2
    assert spans[0]["sectionPath"] == "Intro"
    assert spans[1]["sectionPath"] == "Body"
