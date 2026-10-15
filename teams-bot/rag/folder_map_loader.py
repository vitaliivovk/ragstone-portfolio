"""Load optional folder-map appendix for the RAG optimizer system prompt."""

from __future__ import annotations

from pathlib import Path

_FOLDER_MAP_PROMPT = Path(__file__).resolve().parent / "folder_map_prompt.md"


def get_rag_optimizer_system_prompt_appendix() -> str:
    """
    Human-maintained map of source_data folders (see .cursor/skills/knowledge-base-curator/folder-map-prompt.md).

    When missing, returns an empty string (optimizer uses base prompt only).
    """
    if not _FOLDER_MAP_PROMPT.is_file():
        return ""
    text = _FOLDER_MAP_PROMPT.read_text(encoding="utf-8").strip()
    if not text:
        return ""
    return "\n\n---\n\n" + text
