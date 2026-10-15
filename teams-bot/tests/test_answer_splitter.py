"""Tests for ``rag.answer_splitter.split_for_messages``.

Splitter rules being verified:
1. Short answers (≤ ``SHORT_ANSWER_MAX_CHARS``) ship as a single message.
2. Single-paragraph answers (no ``\\n\\n``) always ship as a single message.
3. Multi-paragraph answers split on blank-line boundaries.
4. Markdown lists and fenced code blocks are atomic (never split).
5. Short heading lines glue to the following block (no orphan headings).
6. Paragraphs shorter than ``MIN_PARAGRAPH_CHARS`` merge with the previous block.
7. Hard cap of ``MAX_MESSAGES`` body messages, with surplus merged at smallest gaps.
"""
from __future__ import annotations

import pytest

from rag.answer_splitter import (
    MAX_MESSAGES,
    MIN_PARAGRAPH_CHARS,
    SHORT_ANSWER_MAX_CHARS,
    split_for_messages,
)


def _para(prefix: str, length: int) -> str:
    """Build a paragraph that comfortably exceeds the merge threshold."""
    pad = "x" * max(0, length - len(prefix))
    return f"{prefix} {pad}".strip()


def test_empty_input_returns_no_messages() -> None:
    assert split_for_messages("") == []
    assert split_for_messages("   \n\n   ") == []


def test_short_single_paragraph_ships_as_one_message() -> None:
    text = "Cześć! Jak mogę pomóc?"
    assert split_for_messages(text) == [text]


def test_short_multi_paragraph_ships_as_one_message() -> None:
    # Total length under the short-answer threshold → still one bubble.
    text = "Pierwszy akapit.\n\nDrugi akapit."
    assert len(text) <= SHORT_ANSWER_MAX_CHARS
    assert split_for_messages(text) == [text]


def test_long_single_paragraph_ships_as_one_message() -> None:
    text = _para("Wyjaśnienie:", SHORT_ANSWER_MAX_CHARS + 200)
    assert "\n\n" not in text
    assert split_for_messages(text) == [text]


def test_two_long_paragraphs_split_into_two_messages() -> None:
    p1 = _para("Akapit pierwszy.", 400)
    p2 = _para("Akapit drugi.", 400)
    text = f"{p1}\n\n{p2}"
    chunks = split_for_messages(text)
    assert chunks == [p1, p2]


def test_short_heading_glues_to_next_paragraph() -> None:
    heading = "**Etapy procesu**"
    body = _para("Najpierw klient kontaktuje się z asystentem.", 400)
    follow = _para("Następnie doradca przygotowuje ofertę.", 400)
    text = f"{heading}\n\n{body}\n\n{follow}"
    chunks = split_for_messages(text)
    assert len(chunks) == 2
    assert chunks[0].startswith(heading)
    assert body in chunks[0]
    assert chunks[1] == follow


def test_markdown_list_is_kept_as_single_message() -> None:
    intro = _para("Wstęp do listy z wymaganiami.", 400)
    list_block = (
        "- pierwszy punkt z dokumentem klienta\n"
        "- drugi punkt z weryfikacją tożsamości\n"
        "- trzeci punkt z podpisaniem umowy"
    )
    text = f"{intro}\n\n{list_block}"
    chunks = split_for_messages(text)
    assert any("pierwszy punkt" in c and "trzeci punkt" in c for c in chunks)
    # All three list items must live in the same chunk: 3 lines starting with "- ".
    for chunk in chunks:
        if "pierwszy punkt" in chunk:
            assert chunk.count("\n- ") == 3


def test_fenced_code_block_is_kept_atomic() -> None:
    intro = _para("Przykład komendy do uruchomienia w terminalu.", 400)
    code = "```bash\ndocker compose up\ndocker compose logs -f\n```"
    follow = _para("Po uruchomieniu sprawdź logi.", 400)
    text = f"{intro}\n\n{code}\n\n{follow}"
    chunks = split_for_messages(text)
    code_chunks = [c for c in chunks if "```bash" in c]
    assert len(code_chunks) == 1
    assert "docker compose up" in code_chunks[0]
    assert "docker compose logs -f" in code_chunks[0]


def test_short_paragraph_merges_with_previous() -> None:
    p1 = _para("Główna treść z wieloma szczegółami procesu.", 400)
    short = "Krótka uwaga końcowa."
    p3 = _para("Trzeci długi akapit z osobnym tematem.", 400)
    assert len(short) < MIN_PARAGRAPH_CHARS
    text = f"{p1}\n\n{short}\n\n{p3}"
    chunks = split_for_messages(text)
    assert len(chunks) == 2
    assert short in chunks[0]
    assert chunks[1] == p3


def test_message_cap_merges_excess_paragraphs() -> None:
    paragraphs = [_para(f"Akapit {i} z opisem dla testu cap.", 200) for i in range(12)]
    text = "\n\n".join(paragraphs)
    chunks = split_for_messages(text)
    assert len(chunks) <= MAX_MESSAGES
    rejoined = "\n\n".join(chunks)
    for paragraph in paragraphs:
        assert paragraph in rejoined  # no content dropped during cap-driven merging


def test_realistic_long_answer_produces_capped_bubbles() -> None:
    intro = _para("Poniżej opisuję proces krok po kroku.", 250)
    sections = []
    for label in ("Rezerwacja", "Weryfikacja", "Umowa", "Wpłata kaucji",
                  "Wydanie kluczy", "Po zakończeniu najmu"):
        sections.append(f"**{label}**\n\n{_para(f'Szczegóły dla etapu {label}.', 350)}")
    tldr = "**TL;DR:** standardowy przebieg z 6 etapami zgodny z dokumentacją."
    text = "\n\n".join([intro, *sections, tldr])

    chunks = split_for_messages(text)
    assert 1 <= len(chunks) <= MAX_MESSAGES
    rejoined = "\n\n".join(chunks)
    assert "Rezerwacja" in rejoined
    assert "TL;DR" in rejoined


@pytest.mark.parametrize(
    "heading",
    [
        "Etapy:",  # has terminal punctuation → not a heading
        "To jest pełne zdanie kończące się kropką.",  # too long-ish + terminal punct
    ],
)
def test_lines_with_terminal_punctuation_are_not_headings(heading: str) -> None:
    body = _para("Treść pierwszego akapitu, dłuższa niż próg.", 400)
    follow = _para("Drugi akapit z ciągiem dalszym.", 400)
    text = f"{heading}\n\n{body}\n\n{follow}"
    chunks = split_for_messages(text)
    # The "heading"-like line ends in punctuation, so it's NOT glued — it stands as its
    # own block (then the min-paragraph merge may combine it with the next).
    assert any(heading in chunk for chunk in chunks)
