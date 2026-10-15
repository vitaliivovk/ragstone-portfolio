"""Slash command parsing for /style."""

from __future__ import annotations

from bot.style_commands import normalize_style_slash_command, parse_style_command


def test_normalize_strips_at_bot_suffix() -> None:
    assert normalize_style_slash_command("/style@NorthwindBot") == "/style"
    assert normalize_style_slash_command("/Style reset@Bot") == "/style reset"


def test_parse_style_get() -> None:
    assert parse_style_command("/style", "/style") == ("get", "")
    assert parse_style_command("/styl", "/styl") == ("get", "")


def test_parse_style_clear() -> None:
    assert parse_style_command("/style reset", "/style reset") == ("clear", "")
    assert parse_style_command("/style wyczyść", "/style wyczyść") == ("clear", "")


def test_parse_style_set() -> None:
    assert parse_style_command("/style krótko", "/style krótko") == ("set", "krótko")
    assert parse_style_command("/styl a b", "/Styl a b") == ("set", "a b")


def test_parse_style_empty_body_is_get() -> None:
    assert parse_style_command("/style ", "/style   ") == ("get", "")


def test_parse_non_style_returns_none() -> None:
    assert parse_style_command("/clean_chat_history", "/clean_chat_history") is None
