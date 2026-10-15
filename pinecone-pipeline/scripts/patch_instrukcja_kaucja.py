#!/usr/bin/env python3
"""Patch Instrukcja 2025 — deposit tiers after client verification (page ~10)."""

from __future__ import annotations

import sys
from pathlib import Path

from docx import Document

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCX_PATH = (
    REPO_ROOT
    / "pinecone-pipeline"
    / "source_data"
    / "5 Instrukcje"
    / "Instrukcja dla nowego pracownika 2025.docx"
)

OLD_PREFIX = "Wysokość kaucji wynika wprost w wyniku weryfikacji klienta"
OLD_FULL = (
    "Wysokość kaucji wynika wprost w wyniku weryfikacji klienta "
    "i jest szczegółowo opisana na mapie procesu – załącznik nr…."
)
NEW_TEXT = (
    "Wysokość kaucji wynika wprost w wyniku weryfikacji klienta: "
    "Weryfikacja przez Northwind obejmuje tożsamość, dochód, "
    "biuro kredytowe i rejestr długów oraz listy sankcyjne UE. "
    "Jeśli weryfikacja jest pozytywna – kaucja wynosi standardową kwotę z wewnętrznego cennika. "
    "Jeśli weryfikacja finansowa jest negatywna – kaucja jest wyższa według tego cennika. "
    "Przy negatywnym wyniku weryfikacji tożsamości lub list sankcyjnych – brak zgody na najem. "
    "Dla manualnej weryfikacji decyduje osoba weryfikująca."
)


def _patch_paragraph(paragraph_text: str) -> str | None:
    if OLD_PREFIX not in paragraph_text:
        return None
    if paragraph_text.strip() == NEW_TEXT.strip():
        return None
    if OLD_FULL in paragraph_text:
        return paragraph_text.replace(OLD_FULL, NEW_TEXT)
    if paragraph_text.startswith(OLD_PREFIX):
        return NEW_TEXT
    return None


def main() -> int:
    if not DOCX_PATH.is_file():
        print(f"Missing docx: {DOCX_PATH}", file=sys.stderr)
        return 1

    document = Document(str(DOCX_PATH))
    patched = 0
    for paragraph in document.paragraphs:
        updated = _patch_paragraph(paragraph.text)
        if updated is None:
            continue
        paragraph.text = updated
        patched += 1

    if patched == 0:
        print("No matching paragraph found (already patched?)", file=sys.stderr)
        return 1

    document.save(str(DOCX_PATH))
    print(f"Patched {patched} paragraph(s) in {DOCX_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
