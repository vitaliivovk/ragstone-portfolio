"""SharePoint document URLs and citation formatting for Teams **Źródła**."""
import os
import re
import urllib.parse
from collections import defaultdict
from typing import Any, Dict, List, Optional

def normalize_page_number(value: Any) -> Optional[int]:
    """
    Return a 1-based integer page for display and deep links, or None if unknown.

    Accepts ints, whole floats (e.g. 1.0 from JSON), or numeric strings; rejects
    non-integer floats so we never show fractional «pages».
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 1 else None
    if isinstance(value, float):
        if value != value:
            return None
        rounded = round(value)
        if abs(value - rounded) > 1e-9:
            return None
        return int(rounded) if rounded >= 1 else None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return normalize_page_number(float(stripped.replace(",", ".")))
        except ValueError:
            return None
    return None


_CITATIONS_USED_LINE = re.compile(
    r"(?:^|\n)\s*CITATIONS_USED:\s*([\d,\s]*)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def streaming_answer_visible_prefix(accumulated: str) -> str:
    """
    Hide a **fully formed** trailing legacy ``CITATIONS_USED:`` line from streamed text.

    Legacy ``CITATIONS_USED:`` tails are hidden so older model output does not flash
    the machine line once the regex matches the buffer tail.
    """
    if not accumulated:
        return ""
    match = _CITATIONS_USED_LINE.search(accumulated)
    if match:
        return accumulated[: match.start()].rstrip()
    return accumulated

# User-facing label is Polish «Źródło»; accept legacy English «Citation» in model output too.
_BRACKET_INLINE_SOURCE = re.compile(r"\[(?:Citation|Źródło)\s*(\d+)\]", re.IGNORECASE)
_PAREN_INLINE_SOURCE = re.compile(r"\((?:Citation|Źródło)\s*(\d+)\)", re.IGNORECASE)
# e.g. [Citation 16, Citation 2] or [Źródło 1, Źródło 3]
_BRACKET_INLINE_MULTI = re.compile(
    r"\[((?:(?:Citation|Źródło)\s*\d+)(?:\s*,\s*(?:Citation|Źródło)\s*\d+)+)\]",
    re.IGNORECASE,
)

# Comma-separated run of two or more inline source brackets, e.g. ``[Źródło 1], [Źródło 2]``.
_COMMA_SEPARATED_BRACKET_RUN = re.compile(
    r"\[(?:Citation|Źródło)\s*\d+\](?:\s*,\s*\[(?:Citation|Źródło)\s*\d+\])+",
    re.IGNORECASE,
)


def sharepoint_library_base_url() -> str:
    """
    Folder base URL for building document links from ``sourceRelativePath``.

    Prefer ``SHAREPOINT_LIBRARY_BASE_URL`` (bot / Function App). Fall back to
    ``SHAREPOINT_BASE_URL`` so the same value used at Pinecone ingest time can
    resolve links without duplicating secrets under two names.
    """
    for env_key in ("SHAREPOINT_LIBRARY_BASE_URL", "SHAREPOINT_BASE_URL"):
        candidate = os.environ.get(env_key, "").strip()
        if candidate:
            return candidate
    return ""


def _normalize_source_relative_path(value: Any) -> Optional[str]:
    """Normalize corpus-relative path for URL joining (forward slashes, trim)."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("\\", "/")
    while "//" in text:
        text = text.replace("//", "/")
    text = text.strip("/")
    return text or None


def resolve_sharepoint_document_url(metadata: Dict[str, Any]) -> Optional[str]:
    """
    Return file URL for SharePoint: use stored sharepointUrl, or join the
    configured library base URL with ``sourceRelativePath`` (mirror corpus layout).

    Base URL: :func:`sharepoint_library_base_url` (``SHAREPOINT_LIBRARY_BASE_URL`` or
    ``SHAREPOINT_BASE_URL``).
    """
    existing = metadata.get("sharepointUrl")
    if existing:
        return str(existing)
    base = sharepoint_library_base_url()
    rel = _normalize_source_relative_path(metadata.get("sourceRelativePath"))
    if not base or not rel:
        return None
    segments = [segment for segment in rel.split("/") if segment]
    if not segments:
        return None
    encoded = "/".join(urllib.parse.quote(segment, safe="") for segment in segments)
    return f"{base.rstrip('/')}/{encoded}"


# Path suffixes where ``?web=1`` opens SharePoint/Office in the browser instead of downloading.
_SHAREPOINT_CITATION_OFFICE_SUFFIXES: tuple[str, ...] = (
    ".docx",
    ".doc",
    ".docm",
    ".pptx",
    ".ppt",
    ".pptm",
    ".potx",
    ".xlsx",
    ".xls",
    ".xlsm",
    ".xlsb",
    ".vsdx",
    ".vsd",
    ".one",
)


def sharepoint_document_open_url(sharepoint_url: str) -> str:
    """
    Return a citation link URL: no fragment; no ``?page=`` / ``find=``.

    * **PDF** — plain file URL (in-browser PDF handling).
    * **Office** (Word, PowerPoint, Excel, …) — append ``?web=1`` so Teams and
      browsers open Office on the web instead of downloading the binary.

    Page numbers stay in the markdown label only, not in the query string.
    """
    if not sharepoint_url:
        return ""
    base = sharepoint_url.split("?", 1)[0].split("#", 1)[0]
    lower = base.lower()
    if lower.endswith(".pdf"):
        return base
    for suffix in _SHAREPOINT_CITATION_OFFICE_SUFFIXES:
        if lower.endswith(suffix):
            return f"{base}?web=1"
    return base


def build_sharepoint_link(
    sharepoint_url: str,
    page_number: Optional[int] = None,
    highlight_phrase: Optional[str] = None,
) -> str:
    """
    Build a SharePoint deep link with optional text highlighting.

    Prefer :func:`sharepoint_document_open_url` for user-facing bibliography links.
    """
    if not sharepoint_url:
        return ""

    lower_url = sharepoint_url.lower()

    params: dict[str, str] = {}

    if lower_url.endswith(".pdf"):
        if page_number:
            params["page"] = str(page_number)
    else:
        params["web"] = "1"
        if highlight_phrase:
            params["find"] = highlight_phrase

    if not params:
        return sharepoint_url

    separator = "&" if "?" in sharepoint_url else "?"
    query_string = urllib.parse.urlencode(params, safe="")

    return f"{sharepoint_url}{separator}{query_string}"


def indices_from_inline_source_brackets(answer_text: str) -> List[int]:
    """
    1-based indices from ``[Źródło N]`` / ``[Citation N]`` in first-seen order (deduped).

    The system prompt requires ``N`` to match CONTEXT fragment numbers. This list is the
    **only** source of truth for which retrieved fragments to attach in **Źródła**.
    """
    if not (answer_text or "").strip():
        return []
    ordered: List[int] = []
    seen: set[int] = set()
    for match in _BRACKET_INLINE_SOURCE.finditer(answer_text):
        value = int(match.group(1))
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def same_doc_comma_citation_collapse_enabled() -> bool:
    raw = os.environ.get("RAG_INLINE_SAME_DOC_CITATION_COLLAPSE_ENABLED", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _source_row_path_key(source_row: dict) -> str:
    return str(source_row.get("sourceRelativePath") or source_row.get("fileName") or "")


def collapse_same_document_comma_citation_runs(
    text: str,
    cite_idx: List[int],
    sources: list[dict],
) -> tuple[str, List[int]]:
    """
    Replace ``[Źródło a], [Źródło b], …`` with a single ``[Źródło k]`` when every index maps
    to the same document path — keeps the smallest fragment index (earliest in CONTEXT).

    Applied right-to-left so spans stay valid. Updates ``cite_idx`` so the bibliography matches
    the visible inline tags.
    """
    if not (text or "").strip() or not sources:
        return text, cite_idx
    cite_idx_work = list(cite_idx)
    out_text = text
    matches = list(_COMMA_SEPARATED_BRACKET_RUN.finditer(text))
    for match in reversed(matches):
        run = match.group(0)
        nums = [int(m.group(1)) for m in _BRACKET_INLINE_SOURCE.finditer(run)]
        if len(nums) < 2:
            continue
        paths: list[str] = []
        invalid = False
        for num in nums:
            if not (1 <= num <= len(sources)):
                invalid = True
                break
            paths.append(_source_row_path_key(sources[num - 1]))
        if invalid or len(set(paths)) != 1:
            continue
        keeper = min(nums)
        replacement = f"[Źródło {keeper}]"
        out_text = out_text[: match.start()] + replacement + out_text[match.end() :]
        num_set = set(nums)
        cite_idx_work = [x for x in cite_idx_work if x not in num_set or x == keeper]
    return out_text, cite_idx_work


def strip_trailing_citations_used_line(answer_text: str) -> str:
    """
    Remove a trailing legacy ``CITATIONS_USED:`` machine line if present.

    Indices on that line are ignored — bibliography uses inline ``[Źródło N]`` only.
    """
    if not (answer_text or "").strip():
        return ""
    match = _CITATIONS_USED_LINE.search(answer_text)
    if not match:
        return answer_text.strip()
    return answer_text[: match.start()].rstrip()


def strip_inline_source_citation_markers(answer_text: str) -> str:
    """
    Remove inline ``[Źródło N]`` / ``[Citation N]`` / ``(Źródło N)`` and multi-bracket runs.

    Call **after** :func:`remap_inline_citation_numbers` so CONTEXT indices are already
    resolved; the final user-visible body omits these tags because **Źródła** carries links.

    This is **post-processing** (not the prompt alone): the model must still emit tags so
    we can map CONTEXT → bibliography; tags are stripped only in the shipped assistant text.

    Normalizes a few full-width bracket variants some models emit, then runs replacements
    in a loop so ``[Źródło 1][Źródło 1]`` collapses cleanly.
    """
    if not (answer_text or "").strip():
        return answer_text or ""
    text = (
        answer_text.replace("\uff3b", "[")
        .replace("\uff3d", "]")
        .replace("\uff08", "(")
        .replace("\uff09", ")")
        .replace("［", "[")
        .replace("］", "]")
        .replace("（", "(")
        .replace("）", ")")
    )
    for _ in range(32):
        prev = text
        text = _BRACKET_INLINE_MULTI.sub("", text)
        text = _BRACKET_INLINE_SOURCE.sub("", text)
        text = _PAREN_INLINE_SOURCE.sub("", text)
        if text == prev:
            break
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _citation_document_key(meta: dict) -> str:
    path = str(meta.get("sourceRelativePath") or "").strip()
    if path:
        return path
    return str(meta.get("fileName") or "").strip()


def _collect_page_numbers_from_citation_row(meta: dict) -> list[int]:
    """Sorted unique 1-based page numbers named on this metadata row."""
    found: set[int] = set()
    for key in ("pageNumber", "_pageEnd"):
        page_n = normalize_page_number(meta.get(key))
        if page_n is not None:
            found.add(page_n)
    extra = meta.get("_citationPages")
    if isinstance(extra, list):
        for item in extra:
            page_n = normalize_page_number(item)
            if page_n is not None:
                found.add(page_n)
    return sorted(found)


def aggregate_citation_rows_by_document(rows: list[dict]) -> list[dict]:
    """
    Merge bibliography rows that refer to the same file into one row.

    Page numbers from all merged rows are collected into ``_citationPages`` (ascending,
    unique). Document order follows first appearance in ``rows``.
    """
    if not rows:
        return []
    out: list[dict] = []
    key_to_out_index: dict[str, int] = {}
    for row in rows:
        key = _citation_document_key(row)
        if not key:
            key = str(row.get("fileName") or "Dokument")
        pages = _collect_page_numbers_from_citation_row(row)
        if key not in key_to_out_index:
            new_row = dict(row)
            new_row.pop("_pageEnd", None)
            if pages:
                new_row["_citationPages"] = pages
            elif "_citationPages" in new_row and not new_row["_citationPages"]:
                new_row.pop("_citationPages", None)
            key_to_out_index[key] = len(out)
            out.append(new_row)
            continue
        target = out[key_to_out_index[key]]
        merged = set(_collect_page_numbers_from_citation_row(target))
        merged.update(pages)
        if merged:
            target["_citationPages"] = sorted(merged)
        target.pop("_pageEnd", None)
    return out


def filter_sources_by_indices(sources: list[dict], one_based_indices: List[int]) -> list[dict]:
    """Keep source rows matching 1-based indices into the CONTEXT numbering order."""
    out: list[dict] = []
    for idx in one_based_indices:
        if 1 <= idx <= len(sources):
            out.append(sources[idx - 1])
    return out


def merge_adjacent_same_document_chunks(sources: list[dict]) -> list[dict]:
    """
    Merge consecutive chunk rows from the same file into one citation row (link from first chunk).
    """
    if not sources:
        return []

    def path_key(meta: dict) -> str:
        return str(meta.get("sourceRelativePath") or meta.get("fileName") or "")

    by_path: Dict[str, list[dict]] = {}
    for row in sources:
        by_path.setdefault(path_key(row), []).append(row)

    merged: list[dict] = []
    for group in by_path.values():
        group.sort(
            key=lambda x: (
                x.get("chunkIndex") is None,
                int(x["chunkIndex"]) if x.get("chunkIndex") is not None else -1,
            )
        )
        start = 0
        while start < len(group):
            end = start + 1
            while end < len(group):
                a = group[end - 1].get("chunkIndex")
                b = group[end].get("chunkIndex")
                if a is None or b is None:
                    break
                if int(b) != int(a) + 1:
                    break
                end += 1
            run = group[start:end]
            first = dict(run[0])
            if len(run) > 1:
                last = run[-1]
                p0 = normalize_page_number(first.get("pageNumber"))
                p1 = normalize_page_number(last.get("pageNumber"))
                if p0 is not None and p1 is not None and p0 != p1:
                    first["_pageEnd"] = p1
            merged.append(first)
            start = end
    return merged


def merge_sources_for_citation_display(documents: list[dict]) -> list[dict]:
    """
    Collapse duplicate file rows when pageNumber is missing (same doc, different chunks).
    Collects chunk indices into _mergedChunkIndices for display.
    """
    groups: dict[tuple[str, object], list[dict]] = defaultdict(list)
    for doc in documents:
        metadata = doc.get("metadata", doc)
        if not isinstance(metadata, dict):
            continue
        file_name = metadata.get("fileName") or "Dokument"
        page_number = normalize_page_number(metadata.get("pageNumber"))
        key = (file_name, page_number if page_number is not None else "__no_page__")
        groups[key].append(metadata)

    out: list[dict] = []
    for _key, metas in groups.items():
        if len(metas) == 1:
            out.append(metas[0])
            continue
        base = dict(metas[0])
        chunk_indices: list[int] = []
        for meta in metas:
            chunk_index = meta.get("chunkIndex")
            if chunk_index is not None:
                chunk_indices.append(int(chunk_index))
        chunk_indices = sorted(set(chunk_indices))
        if chunk_indices:
            base["_mergedChunkIndices"] = chunk_indices
        out.append(base)
    return out


def citation_display_rows_in_order(picked: list[dict]) -> list[dict]:
    """
    Ordered metadata rows exactly as in the citations block (after dedupe), 1-based index = row order.
    """
    if not picked:
        return []
    merged = merge_sources_for_citation_display(picked)
    seen: set[tuple[str, object, object]] = set()
    rows: list[dict] = []
    for metadata in merged:
        file_name = metadata.get("fileName", "Dokument")
        page_number = normalize_page_number(metadata.get("pageNumber"))
        merged_chunks = metadata.get("_mergedChunkIndices")
        chunk_index = metadata.get("chunkIndex")
        dedupe_key = (file_name, page_number, tuple(merged_chunks) if merged_chunks else chunk_index)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        rows.append(metadata)
    return rows


def _metadata_in_display_row(meta: dict, row: dict) -> bool:
    """Whether CONTEXT chunk meta maps to this bibliography row (same document key)."""
    return _citation_document_key(meta) == _citation_document_key(row) and bool(
        _citation_document_key(meta)
    )


def build_context_index_to_display_map(
    full_sources: list[dict],
    cite_idx: list[int],
    display_rows: list[dict],
) -> dict[int, int]:
    """
    Map CONTEXT 1-based index (as in [Źródło N] in CONTEXT) -> 1-based row in Źródła list.
    """
    out: dict[int, int] = {}
    for ctx_idx in cite_idx:
        if not (1 <= ctx_idx <= len(full_sources)):
            continue
        meta = full_sources[ctx_idx - 1]
        for pos, row in enumerate(display_rows, start=1):
            if _metadata_in_display_row(meta, row):
                out[ctx_idx] = pos
                break
    return out


def precompute_streaming_citation_map(
    sources: list[dict],
) -> tuple[dict[int, int], list[dict], int]:
    """Build a CONTEXT-index → display-row map deterministically from retrieved sources.

    Returns a tuple ``(context_to_display, display_rows, max_display)`` where:

    * ``context_to_display[ctx_idx]`` maps a 1-based CONTEXT index to a 1-based
      bibliography row. **All chunks from the same document** share one row
      (first-seen document order in ``sources``). Page numbers accumulate in
      ``_citationPages`` on that row for the **Źródła** label.
    * ``display_rows`` matches what :func:`format_citations_from_display_rows` renders.
    * ``max_display = len(display_rows)``.

    The ``context_to_display`` map is retained for tests and legacy helpers; live
    streaming no longer rewrites ``[Źródło N]``. Chunks with no known page still collapse
    onto their file's single row; they do not add to ``_citationPages``.
    """
    context_to_display: dict[int, int] = {}
    display_rows: list[dict] = []
    doc_key_to_row_no: dict[str, int] = {}
    for ctx_idx, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            continue
        doc_key = _citation_document_key(source)
        if not doc_key:
            doc_key = str(source.get("fileName") or "Dokument")
        page_number = normalize_page_number(source.get("pageNumber"))
        if doc_key not in doc_key_to_row_no:
            row_no = len(display_rows) + 1
            doc_key_to_row_no[doc_key] = row_no
            row = dict(source)
            pages: list[int] = []
            if page_number is not None:
                pages.append(page_number)
            if pages:
                row["_citationPages"] = pages
            display_rows.append(row)
        else:
            row_no = doc_key_to_row_no[doc_key]
            row = display_rows[row_no - 1]
            if page_number is not None:
                existing = row.get("_citationPages")
                if not isinstance(existing, list):
                    existing = []
                if page_number not in existing:
                    existing.append(page_number)
                row["_citationPages"] = sorted(existing)
        context_to_display[ctx_idx] = doc_key_to_row_no[doc_key]
    return context_to_display, display_rows, len(display_rows)


# Substring of "CITATIONS_USED:" — used to detect *partial* trailing fragments
# during streaming so we can hide a half-typed legacy machine line before the model
# completes it. Kept uppercase: comparisons happen on ``.upper()`` of the tail.
_LEGACY_CITATIONS_USED_TOKEN = "CITATIONS_USED:"


def _truncate_unclosed_inline_bracket(text: str) -> str:
    """Hide a trailing ``[`` that has not yet been closed by ``]``.

    Streaming a half-formed inline tag like ``"[Źródło 1"`` is unsafe: when the
    model finally closes it, :func:`remap_inline_citation_numbers` may shrink or
    rewrite the bracket region (e.g. ``[Źródło 12]`` → ``[Źródło 5]``) and the
    new buffer would no longer be a strict extension of what we already shipped.
    We therefore drop everything from the most recent unclosed ``[`` onward; that
    text is shown on the next chunk once the closing ``]`` arrives.
    """
    last_open = text.rfind("[")
    if last_open == -1:
        return text
    if "]" in text[last_open:]:
        return text
    return text[:last_open]


def _truncate_partial_citations_used_line(text: str) -> str:
    """Hide a trailing fragment that could be the start of a ``CITATIONS_USED:`` line.

    :func:`streaming_answer_visible_prefix` only matches a *fully formed* trailing
    legacy machine line. During streaming we may see partial states like
    ``"…\\nCITAT"`` or ``"…\\nCITATIONS_USED: 1"`` between token batches. If we
    leave them visible in chunk T and then the regex finally matches in chunk T+1
    (stripping the entire line), the visible text would shrink and break Teams'
    strict prefix-extension contract. Hiding the partial fragment up front keeps
    the visible buffer monotonically growing.
    """
    if not text:
        return text
    last_nl = text.rfind("\n")
    after_nl = last_nl + 1
    tail = text[after_nl:].lstrip()
    if not tail:
        return text
    upper_tail = tail.upper()
    if (
        _LEGACY_CITATIONS_USED_TOKEN.startswith(upper_tail)
        or upper_tail.startswith(_LEGACY_CITATIONS_USED_TOKEN)
    ):
        cut = last_nl if last_nl >= 0 else 0
        return text[:cut]
    return text


def streaming_safe_answer_visible_text(buffer: str) -> str:
    """
    Text to stream while the model is still writing: hide a fully-formed legacy
    ``CITATIONS_USED:`` tail and any partial tail that could shrink on the next token.

    The model must **not** emit ``[Źródło N]`` tags anymore; there is no remap step.
    """
    if not buffer:
        return ""
    visible = streaming_answer_visible_prefix(buffer)
    visible = _truncate_partial_citations_used_line(visible)
    visible = _truncate_unclosed_inline_bracket(visible)
    return visible


def streaming_safe_remapped_text(
    buffer: str,
    context_to_display: dict[int, int],
    max_display: int,
) -> str:
    """Backward-compatible wrapper; arguments ignored. Prefer :func:`streaming_safe_answer_visible_text`."""
    _ = (context_to_display, max_display)
    return streaming_safe_answer_visible_text(buffer)


def format_citations_from_display_rows(display_rows: list[dict]) -> str:
    """Render a numbered ``Źródła`` list from a precomputed display-row list.

    Rows are one per document from :func:`precompute_streaming_citation_map` (or
    :func:`aggregate_citation_rows_by_document` on the non-streaming path).
    ``_citationPages`` carries merged page numbers for the visible label; links
    use :func:`sharepoint_document_open_url` (no ``?page=`` / ``find=``).
    """
    if not display_rows:
        return ""
    citations: list[str] = []
    for metadata in display_rows:
        file_name = metadata.get("fileName", "Dokument")
        page_number = normalize_page_number(metadata.get("pageNumber"))
        page_number_end = normalize_page_number(metadata.get("_pageEnd"))
        section_title = metadata.get("sectionTitle")
        sharepoint_url = metadata.get("sharepointUrl") or resolve_sharepoint_document_url(metadata)
        highlight_phrase = metadata.get("highlightPhrase")
        pages_extra = metadata.get("_citationPages")
        aggregated_pages: Optional[list[int]] = None
        if isinstance(pages_extra, list) and pages_extra:
            unique_pages: set[int] = set()
            for item in pages_extra:
                page_n = normalize_page_number(item)
                if page_n is not None:
                    unique_pages.add(page_n)
            if unique_pages:
                aggregated_pages = sorted(unique_pages)
        citations.append(
            format_citation(
                file_name=file_name,
                section_title=section_title,
                page_number=page_number,
                page_number_end=page_number_end,
                sharepoint_url=sharepoint_url,
                highlight_phrase=highlight_phrase,
                source_relative_path=None,
                aggregated_pages=aggregated_pages,
            )
        )
    return "\n".join(f"{idx}. {c}" for idx, c in enumerate(citations, start=1))


def remap_inline_citation_numbers(
    answer_text: str,
    context_to_display: dict[int, int],
    max_display: int,
) -> str:
    """
    Rewrite inline refs so numbers match the final **Źródła** list (1..max_display).
    Drops references to CONTEXT indices that do not map to a list row and numbers above max_display.
    """

    def map_context_or_display(n: int) -> Optional[int]:
        if n in context_to_display:
            return context_to_display[n]
        if 1 <= n <= max_display:
            return n
        return None

    def repl_multi(m: re.Match[str]) -> str:
        inner = m.group(1)
        raw_nums = re.findall(r"(?:Citation|Źródło)\s*(\d+)", inner, flags=re.IGNORECASE)
        parts: list[str] = []
        for ns in raw_nums:
            d = map_context_or_display(int(ns))
            if d is not None:
                parts.append(f"[Źródło {d}]")
        return " ".join(parts) if parts else ""

    def repl_bracket(m: re.Match[str]) -> str:
        n = int(m.group(1))
        d = map_context_or_display(n)
        if d is None:
            return ""
        return f"[Źródło {d}]"

    def repl_paren(m: re.Match[str]) -> str:
        n = int(m.group(1))
        d = map_context_or_display(n)
        if d is None:
            return ""
        return f"(Źródło {d})"

    text = _BRACKET_INLINE_MULTI.sub(repl_multi, answer_text)
    text = _BRACKET_INLINE_SOURCE.sub(repl_bracket, text)
    text = _PAREN_INLINE_SOURCE.sub(repl_paren, text)
    return text


def format_citation(
    file_name: str,
    section_title: Optional[str] = None,
    page_number: Optional[int] = None,
    page_number_end: Optional[int] = None,
    sharepoint_url: Optional[str] = None,
    highlight_phrase: Optional[str] = None,
    source_relative_path: Optional[str] = None,
    aggregated_pages: Optional[list[int]] = None,
) -> str:
    """
    Format a single citation with optional markdown link.

    Page numbers appear only in the label. The URL uses :func:`sharepoint_document_open_url`
    (PDF = bare URL; Word/PowerPoint/Excel = ``?web=1`` for in-browser open, no ``find=``).
    """
    _ = highlight_phrase  # Bibliography links are document-level only.
    page_number = normalize_page_number(page_number)
    page_number_end = normalize_page_number(page_number_end)

    parts = [file_name]

    if section_title:
        parts.append(f" — {section_title}")

    if aggregated_pages:
        unique_sorted = sorted({int(p) for p in aggregated_pages if p is not None and p >= 1})
        if unique_sorted:
            parts.append(", str. " + ", ".join(str(p) for p in unique_sorted))
    elif page_number is not None and page_number_end is not None and page_number_end != page_number:
        parts.append(f", str. {page_number}–{page_number_end}")
    elif page_number is not None:
        parts.append(f", str. {page_number}")

    display_text = "".join(parts)

    if sharepoint_url:
        link = sharepoint_document_open_url(sharepoint_url)
        return f"📖 [{display_text}]({link})"
    return f"📖 {display_text}"


def format_citations(documents: list[dict]) -> str:
    """
    Format a list of source documents as citations (one row per file after aggregation).
    """
    if not documents:
        return ""
    rows = citation_display_rows_in_order(documents)
    rows = aggregate_citation_rows_by_document(rows)
    return format_citations_from_display_rows(rows)


def should_attach_source_block(answer_text: str) -> bool:
    """
    When the model states that documentation does not contain the answer, omit the citations block
    so citations are not presented as evidence for a negative claim.

    If the answer still contains legacy inline ``[Źródło N]`` / ``[Citation N]`` (e.g. old model
    output), always attach the bibliography so partial „nie znalazłem…” phrases do not suppress
    sources for the rest of the answer.
    """
    if not (answer_text or "").strip():
        return True
    if _BRACKET_INLINE_SOURCE.search(answer_text) or _PAREN_INLINE_SOURCE.search(answer_text):
        return True
    low = answer_text.lower()
    refusal_markers = (
        "nie znalazłem tej informacji w dokumentacji",
        "nie znalazłam tej informacji w dokumentacji",
        "nie znalazłem odpowiedzi w dokumentacji",
        "nie znalazłam odpowiedzi w dokumentacji",
        "nie znaleziono informacji w dokumentacji",
        "nie znaleziono odpowiedzi w dokumentacji",
        "nie znaleziono",
        "brak w dokumentacji",
        "brak informacji w dokumentacji",
        "nie ma w dokumentacji",
        "nie ma takiej informacji",
        "nie zawiera dokumentacja",
    )
    return not any(marker in low for marker in refusal_markers)
