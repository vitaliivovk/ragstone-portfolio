"""Split a fully-formed answer into one Teams message per logical paragraph.

Replaces the previous "stream one giant bubble" delivery with N independent
``type=message`` activities. Splitting on the post-processed answer keeps
behaviour deterministic (no dependence on token-arrival order) and avoids the
``ContentStreamNotAllowed`` class of errors entirely (each message is its own
activity, so there is no prefix-superset invariant to honour).

Public API
----------

``split_for_messages(text)``
    Return the list of message bodies to ship in order. Returns ``[text]``
    unchanged for short / single-paragraph answers (Case 1 in the design); a
    list of grouped paragraphs (Case 2) otherwise. Citations are NOT extracted
    here — the caller appends them as a separate message via
    :func:`rag.citations.format_citations`.
"""
from __future__ import annotations

import re
from typing import List


SHORT_ANSWER_MAX_CHARS = 600
"""Answers at or below this length always ship as a single message (Case 1)."""

MIN_PARAGRAPH_CHARS = 120
"""Paragraphs shorter than this are merged with the previous block."""

MAX_HEADING_CHARS = 80
"""Lines no longer than this with no terminal punctuation are treated as headings."""

MAX_MESSAGES = 6
"""Hard cap on body messages; surplus paragraphs are merged at the smallest gaps."""


_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")
_FENCED_CODE_OPEN = re.compile(r"^\s*```")
_LIST_LINE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
_TERMINAL_PUNCT = (".", "!", "?", ":", ";", "…")


def split_for_messages(text: str) -> List[str]:
    """Return one string per Teams message that should be sent for this answer."""
    body = (text or "").strip()
    if not body:
        return []

    if len(body) <= SHORT_ANSWER_MAX_CHARS or "\n\n" not in body:
        return [body]

    blocks = _split_into_atomic_blocks(body)
    blocks = _glue_headings(blocks)
    blocks = _merge_short_paragraphs(blocks)
    blocks = _enforce_message_cap(blocks, MAX_MESSAGES)
    return [block.strip() for block in blocks if block.strip()]


def _split_into_atomic_blocks(body: str) -> List[str]:
    """Split on blank lines while keeping fenced code blocks and list runs intact."""
    lines = body.split("\n")
    blocks: List[str] = []
    buf: List[str] = []
    in_fence = False
    in_list = False

    def flush() -> None:
        if buf:
            chunk = "\n".join(buf).strip("\n")
            if chunk:
                blocks.append(chunk)
            buf.clear()

    for line in lines:
        if _FENCED_CODE_OPEN.match(line):
            buf.append(line)
            in_fence = not in_fence
            if not in_fence:
                flush()
            continue

        if in_fence:
            buf.append(line)
            continue

        is_list_line = bool(_LIST_LINE.match(line))
        if line.strip() == "":
            if in_list:
                buf.append(line)
                continue
            flush()
            in_list = False
            continue

        if is_list_line:
            in_list = True
            buf.append(line)
            continue

        if in_list and (line.startswith(" ") or line.startswith("\t")):
            buf.append(line)
            continue

        if in_list:
            flush()
            in_list = False

        buf.append(line)

    flush()
    return [_strip_trailing_blank_lines(b) for b in blocks if b.strip()]


def _strip_trailing_blank_lines(block: str) -> str:
    """List blocks may end with the blank line that terminated them — drop it."""
    return block.rstrip()


def _is_heading_line(block: str) -> bool:
    """Heuristic for "this is a heading meant to introduce the next paragraph"."""
    if "\n" in block.strip():
        return False
    line = block.strip()
    if len(line) > MAX_HEADING_CHARS:
        return False
    if line.endswith(_TERMINAL_PUNCT):
        return False
    if _LIST_LINE.match(line):
        return False
    return True


def _glue_headings(blocks: List[str]) -> List[str]:
    """Glue a short heading block to the following block so it never ships alone."""
    if len(blocks) < 2:
        return blocks
    out: List[str] = []
    pending_heading: str | None = None
    for block in blocks:
        if pending_heading is not None:
            out.append(f"{pending_heading}\n\n{block}")
            pending_heading = None
            continue
        if _is_heading_line(block):
            pending_heading = block
            continue
        out.append(block)
    if pending_heading is not None:
        if out:
            out[-1] = f"{out[-1]}\n\n{pending_heading}"
        else:
            out.append(pending_heading)
    return out


def _merge_short_paragraphs(blocks: List[str]) -> List[str]:
    """Merge any block under ``MIN_PARAGRAPH_CHARS`` into the previous one."""
    if not blocks:
        return blocks
    out: List[str] = [blocks[0]]
    for block in blocks[1:]:
        if len(block) < MIN_PARAGRAPH_CHARS:
            out[-1] = f"{out[-1]}\n\n{block}"
        else:
            out.append(block)
    return out


def _enforce_message_cap(blocks: List[str], cap: int) -> List[str]:
    """Cap message count by repeatedly merging the two adjacent shortest blocks."""
    if len(blocks) <= cap:
        return blocks
    work = list(blocks)
    while len(work) > cap:
        merge_at = _smallest_adjacent_pair_index(work)
        merged = f"{work[merge_at]}\n\n{work[merge_at + 1]}"
        work = work[:merge_at] + [merged] + work[merge_at + 2:]
    return work


def _smallest_adjacent_pair_index(blocks: List[str]) -> int:
    """Index ``i`` of the adjacent pair (``i``, ``i+1``) with the smallest combined length."""
    best_index = 0
    best_total = len(blocks[0]) + len(blocks[1])
    for i in range(1, len(blocks) - 1):
        total = len(blocks[i]) + len(blocks[i + 1])
        if total < best_total:
            best_total = total
            best_index = i
    return best_index
