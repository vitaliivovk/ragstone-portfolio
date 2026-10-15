"""Polish status lines for Teams streaming (task 22: workflow milestones, not timers)."""

from __future__ import annotations

# Labels for RetrievalScope slugs (see teams-bot/rag/retrieval_filter.py).
SCOPE_SHORT_LABEL_PL: dict[str, str] = {
    "all": "cała dokumentacja",
    "1_najem_instytucjonalny": "Najem instytucjonalny",
    "2_najem_firma": "Najem dla firm",
    "3_mieszkania_z_vatem_najem_zwyky": "Mieszkania z VAT / najem zwykły",
    "4_umowa_rezerwacyjna": "Umowa rezerwacyjna",
    "5_instrukcje": "Instrukcje",
    "6_program_rabatowy_northwind_club_i_smart_home": "Program Northwind Club / Smart Home",
    "zakwaterowanie": "Zakwaterowanie",
}


def analyzing_question() -> str:
    return "Analizuję pytanie…"


def history_loading_question() -> str:
    return "Wczytuję historię rozmowy…"


def optimizer_planning_message() -> str:
    return "Planuję wyszukiwanie…"


def answer_composing_message() -> str:
    return "Układam odpowiedź…"


def after_optimize_message(
    *,
    needs_rag: bool,
    num_docs: int,
    retrieval_scopes: list[str],
    corpus_path_prefixes: list[str],
    corpus_file_name: str = "",
    corpus_source_relative_path: str = "",
) -> str:
    if not needs_rag:
        return "Układam odpowiedź z kontekstu rozmowy…"
    topic_slugs = [slug.strip() for slug in retrieval_scopes if slug and str(slug).strip()]
    if topic_slugs and topic_slugs != ["all"]:
        labels = [SCOPE_SHORT_LABEL_PL.get(slug, slug) for slug in topic_slugs]
        scope_part = f"Ustalam zakres: {', '.join(labels)}. "
    else:
        scope_part = ""
    k_part = f"Szukam do ok. {num_docs} fragmentów w dokumentacji…"
    doc_parts: list[str] = []
    prefix_rows = [p.strip() for p in corpus_path_prefixes if p and str(p).strip()]
    if prefix_rows:
        doc_parts.append("Filtry folderów: " + "; ".join(prefix_rows))
    if corpus_file_name:
        doc_parts.append(f"Plik: {corpus_file_name}")
    if corpus_source_relative_path:
        doc_parts.append(f"Ścieżka: {corpus_source_relative_path}")
    if doc_parts:
        return f"{scope_part}{'; '.join(doc_parts)}. {k_part}"
    return f"{scope_part}{k_part}".strip()


def after_retrieve_message(num_sources: int, *, fallback_unfiltered: bool) -> str:
    if fallback_unfiltered:
        return (
            "Zawężone wyszukiwanie bez wyniku — przeszukuję szerszy zakres "
            "i łączę kontekst…"
        )
    if num_sources == 0:
        return "Brak trafień w bazie — układam odpowiedź…"
    return (
        f"Łączę kontekst ({num_sources} fragmentów) — układam odpowiedź "
        "na podstawie dokumentów…"
    )


def retrieval_phase_message(phase: str, info: dict) -> str | None:
    if phase == "vector_search":
        return "Szukam najbardziej pasujących fragmentów w dokumentacji…"
    if phase == "scoped_fallback":
        return "Zawężone wyszukiwanie bez wyniku — przeszukuję szerszy zakres…"
    if phase == "neighbor_expansion":
        primary = info.get("primary_rows")
        if primary is not None:
            return (
                f"Rozszerzam kontekst o powiązane fragmenty "
                f"(na bazie {primary} trafień)…"
            )
        return "Rozszerzam kontekst o powiązane fragmenty…"
    if phase == "context_ready":
        return None
    if phase == "cache_hit":
        return "Korzystam z kontekstu z poprzedniego wyszukiwania — układam odpowiedź…"
    if phase == "cache_augment":
        return "Dopasowuję nowe fragmenty do wcześniejszego kontekstu…"
    return None
