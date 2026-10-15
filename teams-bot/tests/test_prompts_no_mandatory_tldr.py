"""Prompt policy: no mandatory TL;DR line in depth instructions."""

from __future__ import annotations

from rag.prompts import ANSWER_DEPTH_INSTRUCTIONS, SYSTEM_PROMPT


def test_standard_depth_has_no_tldr_marker() -> None:
    block = ANSWER_DEPTH_INSTRUCTIONS["standard"]
    assert "**TL;DR:**" not in block
    assert "obowiązkowo" not in block.lower()


def test_detailed_depth_has_no_mandatory_tldr() -> None:
    block = ANSWER_DEPTH_INSTRUCTIONS["detailed"]
    assert "**TL;DR:**" not in block
    assert "obowiązkowo" not in block.lower()


def test_standard_depth_requires_key_points_for_long_answers() -> None:
    block = ANSWER_DEPTH_INSTRUCTIONS["standard"]
    assert "120" in block
    assert "Najważniejsze punkty" in block


def test_detailed_depth_requires_key_points_for_long_answers() -> None:
    block = ANSWER_DEPTH_INSTRUCTIONS["detailed"]
    assert "120" in block
    assert "Najważniejsze punkty" in block


def test_system_prompt_bans_cross_language_acknowledgment_fillers() -> None:
    assert "potwierdzam" in SYSTEM_PROMPT.lower()
    assert "confirmed" in SYSTEM_PROMPT.lower()
    assert "{user_preferences_block}" in SYSTEM_PROMPT
