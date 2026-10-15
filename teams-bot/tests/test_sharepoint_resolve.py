"""SharePoint document URL resolution from Pinecone metadata + env base URL."""

from __future__ import annotations

import pytest

from rag.citations import (
    format_citations_from_display_rows,
    resolve_sharepoint_document_url,
    sharepoint_library_base_url,
)


@pytest.fixture(autouse=True)
def clear_sharepoint_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SHAREPOINT_LIBRARY_BASE_URL", raising=False)
    monkeypatch.delenv("SHAREPOINT_BASE_URL", raising=False)


def test_sharepoint_library_base_url_prefers_library(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHAREPOINT_LIBRARY_BASE_URL", "https://a.example/")
    monkeypatch.setenv("SHAREPOINT_BASE_URL", "https://b.example/")
    assert sharepoint_library_base_url() == "https://a.example/"


def test_sharepoint_library_base_url_falls_back_to_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHAREPOINT_BASE_URL", "https://lib.example/x")
    assert sharepoint_library_base_url() == "https://lib.example/x"


def test_resolve_joins_base_and_encoded_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "SHAREPOINT_BASE_URL",
        "https://tenant.sharepoint.com/sites/S/Shared%20Documents/AI/v3",
    )
    meta = {"sourceRelativePath": "3 Folder/sub/Doc.docx"}
    url = resolve_sharepoint_document_url(meta)
    assert url is not None
    assert url.startswith(
        "https://tenant.sharepoint.com/sites/S/Shared%20Documents/AI/v3/"
    )
    assert "3%20Folder" in url
    assert url.endswith("Doc.docx")


def test_resolve_normalizes_backslashes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHAREPOINT_BASE_URL", "https://example.com/lib")
    meta = {"sourceRelativePath": r"a\b\c.pdf"}
    url = resolve_sharepoint_document_url(meta)
    assert url == "https://example.com/lib/a/b/c.pdf"


def test_metadata_sharepoint_url_wins_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHAREPOINT_BASE_URL", "https://wrong.example/")
    meta = {
        "sharepointUrl": "https://right.sharepoint.com/sites/x/doc.docx",
        "sourceRelativePath": "ignored/path.docx",
    }
    assert resolve_sharepoint_document_url(meta) == "https://right.sharepoint.com/sites/x/doc.docx"


def test_format_citations_from_display_rows_uses_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHAREPOINT_BASE_URL", "https://ex.example/root")
    rows = [
        {
            "fileName": "Przedłużenie.docx",
            "sourceRelativePath": (
                "3 Mieszkania z vatem- najem zwykły/2 Przedłużenie Mieszkania z vatem/"
                "Przedłużenie najmu Z VAT (N) PL_16012026_v.7.docx"
            ),
            "pageNumber": 1,
        }
    ]
    block = format_citations_from_display_rows(rows)
    assert block.startswith("1. 📖 [")
    assert "](https://ex.example/root/3%20Mieszkania" in block
    assert "PL_16012026_v.7.docx" in block
    assert "](" in block
    link_start = block.index("](") + 2
    link_end = block.index(")", link_start)
    url = block[link_start:link_end]
    assert url.endswith(".docx?web=1")
    assert "find=" not in url
