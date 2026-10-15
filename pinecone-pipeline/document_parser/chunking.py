"""Normalize parsed elements and merge them into RAG-sized chunks."""

import json
import re
from typing import Any, Dict, List, Optional, Tuple


def serialize_coordinates(coords: Any) -> Optional[str]:
    """Best-effort serialization of element coordinates to JSON string."""
    if coords is None:
        return None
    try:
        if hasattr(coords, "to_dict"):
            return json.dumps(coords.to_dict(), ensure_ascii=False)
        if hasattr(coords, "__dict__"):
            return json.dumps(coords.__dict__, ensure_ascii=False, default=str)
        return json.dumps(coords, ensure_ascii=False, default=str)
    except Exception:
        return str(coords)


_tiktoken_encoder = None


def _get_encoder():
    global _tiktoken_encoder
    if _tiktoken_encoder is None:
        try:
            import tiktoken  # type: ignore

            _tiktoken_encoder = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _tiktoken_encoder = None
    return _tiktoken_encoder


def count_tokens(text: str) -> int:
    enc = _get_encoder()
    if enc is None:
        return max(1, int(len(text) / 4))
    try:
        return len(enc.encode(text))
    except Exception:
        return max(1, int(len(text) / 4))


def _is_heading(category: str) -> bool:
    c = (category or "").lower()
    return any(k in c for k in ["title", "heading", "header"])


def _extract_unit_fields(elem: Any) -> Tuple[str, Optional[str]]:
    txt = getattr(elem, "text", None)
    if not isinstance(txt, str):
        txt = ""
    html = getattr(getattr(elem, "metadata", None), "text_as_html", None)

    if html and (getattr(elem, "category", "") or "").lower() == "table":
        plain = re.sub(r"<[^>]+>", " ", html)
        plain = re.sub(r"\s+", " ", plain).strip()
        if plain:
            return plain, html
    return txt, html


def normalize_elements_to_units(elements: List[Any]) -> List[Dict[str, Any]]:
    """Normalize unstructured elements into lightweight units for chunking."""
    units: List[Dict[str, Any]] = []
    for block_index, elem in enumerate(elements):
        md = getattr(elem, "metadata", None)
        page_number = None
        slide_number = None
        sheet_name = None
        try:
            page_number = getattr(md, "page_number", None) or getattr(md, "page", None)
        except Exception:
            pass
        try:
            slide_number = getattr(md, "slide_number", None) or getattr(md, "slide", None)
        except Exception:
            pass
        try:
            sheet_name = (
                getattr(md, "sheet_name", None)
                or getattr(md, "sheet", None)
                or getattr(md, "worksheet_name", None)
                or getattr(md, "table_caption", None)
            )
            if not sheet_name and hasattr(md, "coordinates"):
                coords_obj = getattr(md, "coordinates", None)
                if isinstance(coords_obj, dict) and "sheet" in coords_obj:
                    sheet_name = coords_obj["sheet"]
        except Exception:
            pass
        coords = serialize_coordinates(getattr(md, "coordinates", None))

        if not sheet_name and coords:
            try:
                coords_dict = json.loads(coords)
                if isinstance(coords_dict, dict) and "sheet" in coords_dict:
                    sheet_name = coords_dict["sheet"]
            except Exception:
                pass

        category = getattr(elem, "category", elem.__class__.__name__)
        text, html = _extract_unit_fields(elem)
        if not (text or html):
            continue
        units.append(
            {
                "text": text or "",
                "html": html,
                "category": str(category),
                "pageNumber": int(page_number) if page_number is not None else None,
                "slideNumber": int(slide_number) if slide_number is not None else None,
                "sheetName": str(sheet_name) if sheet_name is not None else None,
                "coordinates": coords,
                "isHeading": _is_heading(str(category)),
                "isTable": (str(category).lower() == "table"),
                "blockIndex": block_index,
            }
        )
    return units


def merge_units_into_chunks(
    units: List[Dict[str, Any]],
    target_tokens: int = 300,
    overlap_ratio: float = 0.15,
) -> List[Dict[str, Any]]:
    """Merge adjacent units into RAG-friendly chunks with soft overlap and heading context."""
    chunks: List[Dict[str, Any]] = []
    current_section_path: List[str] = []

    def section_title() -> Optional[str]:
        return current_section_path[-1] if current_section_path else None

    prepared: List[Dict[str, Any]] = []
    for u in units:
        if u["isHeading"]:
            title_text = u.get("text") or u.get("html") or ""
            title_text = re.sub(r"\s+", " ", title_text).strip()
            if title_text:
                current_section_path = [title_text]
            prepared.append({"type": "heading", "unit": u, "tokens": count_tokens(title_text)})
            continue

        text = u.get("text", "")
        tok = count_tokens(text) if text else 0
        prepared.append({"type": "content", "unit": u, "tokens": tok})

    window_tokens = 0
    window_text_parts: List[str] = []
    window_tables_html: List[str] = []
    window_units: List[Dict[str, Any]] = []
    window_contains_table = False
    first_page: Optional[int] = None
    first_coords: Optional[str] = None
    first_sheet: Optional[str] = None
    first_slide: Optional[int] = None

    def flush_chunk() -> None:
        nonlocal window_tokens, window_text_parts, window_tables_html, window_units, window_contains_table, first_page, first_coords, first_sheet, first_slide
        if not window_text_parts and not window_tables_html:
            window_units = []
            window_tokens = 0
            return
        # After a flush we keep overlap text in window_text_parts but clear window_units until
        # the next unit arrives. A later flush with only that overlap (EOF or before a heading)
        # would emit a duplicate tail chunk with no block/page metadata — drop it.
        if not window_units and not window_tables_html:
            window_text_parts = []
            window_tokens = 0
            return
        content_text = "\n\n".join([p for p in window_text_parts if p])
        content_html = "\n\n".join([h for h in window_tables_html if h]) if window_tables_html else None
        element_type = "Table" if (window_contains_table and not content_text.strip()) else ("Mixed" if window_contains_table else "Text")
        block_start_idx: Optional[int] = None
        block_end_idx: Optional[int] = None
        if window_units:
            block_indices = [wu["blockIndex"] for wu in window_units if wu.get("blockIndex") is not None]
            if block_indices:
                block_start_idx = min(block_indices)
                block_end_idx = max(block_indices)
        chunks.append(
            {
                "content": content_text,
                "contentHtml": content_html,
                "isTable": window_contains_table,
                "sectionTitle": section_title(),
                "sectionPath": " > ".join([s for s in current_section_path if s]) if current_section_path else None,
                "pageNumber": first_page,
                "coordinates": first_coords,
                "sheetName": first_sheet,
                "slideNumber": first_slide,
                "elementType": element_type,
                "blockStartIndex": block_start_idx,
                "blockEndIndex": block_end_idx,
            }
        )

        overlap_tokens = int(target_tokens * overlap_ratio)
        if overlap_tokens > 0 and content_text:
            tokens = content_text.split()
            tail_tokens = tokens[-overlap_tokens:]
            window_text_parts = [" ".join(tail_tokens)]
            window_tokens = len(tail_tokens)
        else:
            window_text_parts = []
            window_tokens = 0
        window_tables_html = []
        window_units = []
        window_contains_table = False
        first_page = None
        first_coords = None
        first_sheet = None
        first_slide = None

    current_section_path = []
    for item in prepared:
        u = item["unit"]
        if item["type"] == "heading":
            flush_chunk()
            title_text = u.get("text") or u.get("html") or ""
            title_text = re.sub(r"\s+", " ", title_text).strip()
            current_section_path = [title_text] if title_text else []
            continue

        unit_text = (u.get("text") or "").strip()
        unit_html = u.get("html")
        if first_page is None:
            first_page = u.get("pageNumber")
        if first_coords is None:
            first_coords = u.get("coordinates")
        if first_sheet is None:
            first_sheet = u.get("sheetName")
        if first_slide is None:
            first_slide = u.get("slideNumber")

        if unit_text:
            window_text_parts.append(unit_text)
            window_tokens += item["tokens"]
        if unit_html:
            window_tables_html.append(unit_html)
            window_contains_table = True
        window_units.append(u)

        if window_tokens >= target_tokens:
            flush_chunk()

    flush_chunk()
    return chunks
