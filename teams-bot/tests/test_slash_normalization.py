"""Teams slash-command normalization."""

from __future__ import annotations

from function_app import _normalize_teams_slash_command


def test_normalize_strips_at_mention_suffix() -> None:
    assert _normalize_teams_slash_command("/clean_chat_history@NorthwindAssistantBot") == "/clean_chat_history"


def test_normalize_lowercase_and_trim() -> None:
    assert _normalize_teams_slash_command("  /CLEAN_CHAT_HISTORY  ") == "/clean_chat_history"
