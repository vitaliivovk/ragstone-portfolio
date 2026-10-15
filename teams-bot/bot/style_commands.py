"""Parse Teams /style slash commands (user preference text for the answer model)."""

from __future__ import annotations

from typing import Literal, Tuple


def normalize_style_slash_command(message_text: str) -> str:
    """Lowercase, strip; strip ``@BotName`` suffix from ``/style@Bot``."""
    stripped = message_text.strip().lower()
    if "@" in stripped:
        stripped = stripped.split("@", 1)[0].strip()
    return stripped


StyleCommandKind = Literal["get", "clear", "set"]


def parse_style_command(
    normalized_slash: str, original_message: str
) -> Tuple[StyleCommandKind, str] | None:
    """
    Return ``(kind, payload)`` if this is a ``/style`` command, else ``None``.

    * ``get`` — show current preferences (payload empty).
    * ``clear`` — ``/style reset`` / ``/styl reset`` / ``/style clear``.
    * ``set`` — payload is the preference text (empty payload → ``get``).
    """
    raw = original_message.strip()
    low = raw.lower()
    if low in ("/style", "/styl"):
        return ("get", "")
    for prefix in ("/style ", "/styl "):
        if low.startswith(prefix):
            body = raw[len(prefix) :].strip()
            body_lower = body.lower()
            if body_lower in ("reset", "clear", "wyczysc", "wyczyść"):
                return ("clear", "")
            if not body:
                return ("get", "")
            return ("set", body)
    if normalized_slash in ("/style", "/styl"):
        return ("get", "")
    return None
