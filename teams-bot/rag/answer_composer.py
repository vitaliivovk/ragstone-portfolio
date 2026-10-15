"""Topic-specific answer composition hints for the RAG answer model."""

from __future__ import annotations

_TOPIC_BLOCKS: dict[str, str] = {
    "deposit_kaucja": (
        "**Szablon tematu (kaucja):** Wskaż **jedną zasadę** wyraźnie wynikającą z CONTEXT "
        "(np. pozytywna vs negatywna ścieżka weryfikacji). **Wszystkie kwoty i progi wyłącznie z CONTEXT.** "
        "Gdy fragmenty pochodzą z **różnych dokumentów** lub opisują **różne scenariusze**, wymień pliki "
        "i doprecyzuj brakujący wymiar zamiast scalać reguły w jedną odpowiedź."
    ),
    "verification": (
        "**Szablon tematu (weryfikacja):** Oddziel **weryfikację tożsamości** od **weryfikacji finansowej** "
        "(biuro kredytowe i rejestr długów, dochody). Dla obcokrajowców: PESEL → Northwind; bez PESEL — opisz ścieżkę z CONTEXT "
        "(automatyczna vs manualna), bez domysłów. Przy negatywnej weryfikacji: konsekwencje dla umowy i kaucji "
        "tylko z fragmentów."
    ),
    "early_termination": (
        "**Szablon tematu (wcześniejsze rozwiązanie):** Wskaż **z jakiego dokumentu / scenariusza** "
        "w CONTEXT pochodzi odpowiedź (nazwa pliku z nagłówka fragmentu). "
        "**Nie łącz** reguł z różnych rodzin dokumentów (umowa pierwsza vs przedłużenie vs szablon porozumienia "
        "vs instrukcja procedury) w jedną kwotę — gdy fragmenty dotyczą różnych scenariuszy, wymień je "
        "i doprecyzuj brakujący wymiar. **Wszystkie kwoty i limity wyłącznie z CONTEXT.**"
    ),
}

_NUMERIC_LEAD_RULE = (
    "**Zdanie otwierające (pytanie liczbowe):** Pierwsze zdanie musi zawierać "
    "**bezpośrednią odpowiedź liczbową lub kwotę** (np. wysokość kaucji, liczba miesięcy, minimalna opłata), "
    "jeśli CONTEXT to umożliwia — dopiero potem kontekst i wyjątki."
)


def build_topic_composer_block(answer_topic: str, numeric_answer_first: bool) -> str:
    """Compose optional system-prompt appendix from optimizer fields (no regex on question)."""
    parts: list[str] = []
    if numeric_answer_first:
        parts.append(_NUMERIC_LEAD_RULE)
    topic = (answer_topic or "none").strip().lower()
    if topic != "none":
        block = _TOPIC_BLOCKS[topic]
        if block:
            parts.append(block)
    if not parts:
        return ""
    return "\n\n".join(parts)


def format_clarification_response(questions: list[str]) -> str:
    """Format up to two clarifying questions without retrieval or LLM."""
    trimmed = [str(q).strip() for q in questions if str(q).strip()][:2]
    if not trimmed:
        return (
            "Potrzebuję krótkiego doprecyzowania, żeby odpowiedzieć na podstawie dokumentacji. "
            "Napisz proszę, o który etap, sytuację lub wariant procedury chodzi."
        )
    intro = (
        "Żeby odpowiedzieć precyzyjnie na podstawie dokumentacji, potrzebuję krótkiego doprecyzowania:"
    )
    bullets = "\n".join(f"- {q}" for q in trimmed)
    return f"{intro}\n\n{bullets}"
