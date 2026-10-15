"""User preference prompt block formatting (no Azure I/O)."""

from __future__ import annotations

from rag.user_preferences import format_user_preferences_prompt_block


def test_format_empty_returns_empty_string() -> None:
    assert format_user_preferences_prompt_block("") == ""
    assert format_user_preferences_prompt_block("   ") == ""
    assert format_user_preferences_prompt_block(None) == ""


def test_format_non_empty_includes_header() -> None:
    block = format_user_preferences_prompt_block("  krótko  ")
    assert "**Treść preferencji użytkownika (/style)" in block
    assert "krótko" in block
