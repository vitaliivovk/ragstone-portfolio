"""LLM-based RAG optimization for quality and speed."""
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from .folder_map_loader import get_rag_optimizer_system_prompt_appendix
from .retrieval_filter import RetrievalScope


logger = logging.getLogger(__name__)


_LAST_RETRIEVAL_FILES_LIMIT = 5
"""Cap on file paths shown to the optimizer in the cached-retrieval block (token budget)."""

_LAST_RETRIEVAL_QUERY_CHAR_LIMIT = 240
"""Cap on the cached optimized_query echoed to the optimizer."""


class SearchFocus(str, Enum):
    """Type of search to perform."""
    SPECIFIC = "specific"  # Simple fact lookup, fewer docs
    BROAD = "broad"        # Complex question, more docs needed
    NONE = "none"          # No search needed


class RetrievalTier(str, Enum):
    """How to query Pinecone when RAG is on."""

    CHUNKS_ONLY = "chunks_only"
    SUMMARY_THEN_CHUNKS = "summary_then_chunks"


class AnswerDepth(str, Enum):
    """How verbose the final answer should be."""

    CONCISE = "concise"
    STANDARD = "standard"
    DETAILED = "detailed"


class DirectMode(str, Enum):
    """Which direct-response prompt to use when ``needs_rag`` is false."""

    SMALLTALK = "smalltalk"
    HANDBOOK = "handbook"


class ReusePreviousContext(str, Enum):
    """Whether to skip or narrow vector retrieval using the last cached chunks."""

    NONE = "none"
    REUSE = "reuse"
    AUGMENT = "augment"


class AnswerTopic(str, Enum):
    """Answer-composer template selected by the optimizer (not regex on the question)."""

    NONE = "none"
    DEPOSIT_KAUCJA = "deposit_kaucja"
    VERIFICATION = "verification"
    EARLY_TERMINATION = "early_termination"


class RAGStrategy(BaseModel):
    """
    Routing decision returned by the optimizer LLM.

    Slim by design: each extra field costs output tokens (and, on reasoning
    models, extra latency) on every turn. Audit-only signals such as
    ``search_focus`` / ``retrieval_tier`` / ``reasoning`` were dropped — they
    are either constant (env-controlled) or never read by the retrieval path.
    """

    needs_rag: bool = Field(
        description=(
            "True when the assistant needs to look up documents. False for greetings, confirmations, "
            "meta questions, follow-ups answerable from history, repeat/rephrase requests without new facts, "
            "or internal handbook/process questions served from inlined docs (then set direct_mode=handbook)."
        )
    )
    direct_mode: DirectMode = Field(
        default=DirectMode.SMALLTALK,
        description=(
            "Only when needs_rag is false: use smalltalk for greetings/meta/history-only. "
            "Handbook direct mode is disabled in production — never set handbook; use needs_rag=true "
            "for employee CRM/process and tenant-policy questions (Instrukcja is retrieved via Pinecone/anchor)."
        ),
    )
    optimized_query: str = Field(
        default="",
        description="Polish search query for the vector index. Empty when needs_rag is false.",
    )
    num_documents: int = Field(
        default=6,
        ge=2,
        le=8,
        description="Target chunk count: 2-4 narrow fact, 5-6 typical, 7-8 broad comparison.",
    )
    answer_depth: AnswerDepth = Field(
        default=AnswerDepth.CONCISE,
        description="concise = default short answer; standard = several related points; detailed = full review when scope is clear.",
    )
    retrieval_scopes: List[RetrievalScope] = Field(
        default_factory=lambda: [RetrievalScope.ALL],
        min_length=1,
        max_length=8,
        description="Corpus slug list (OR filter on corpusTopic). Use ['all'] alone when unsure or cross-corpus.",
    )
    corpus_path_prefixes: Optional[List[str]] = Field(
        default=None,
        description="Optional corpusPathPrefix values ('root_slug/sub_slug', OR). Null when scope alone is enough.",
    )
    corpus_file_name: Optional[str] = Field(
        default=None,
        description="Exact Pinecone fileName when the user names a specific file; otherwise null.",
    )
    corpus_source_relative_path: Optional[str] = Field(
        default=None,
        description="Exact sourceRelativePath when the full path is known; otherwise null.",
    )
    reuse_previous_context: ReusePreviousContext = Field(
        default=ReusePreviousContext.NONE,
        description=(
            "none = normal Pinecone retrieval. reuse = prior turn chunks suffice; skip new search. "
            "augment = keep prior chunks and add a small Pinecone top-up."
        ),
    )
    clarification_needed: bool = Field(
        default=False,
        description=(
            "True when the question is too ambiguous to search or answer safely without "
            "1–2 short clarifying questions (max 2). When true, set needs_rag=false and "
            "populate clarification_questions with questions specific to this topic; "
            "do not guess missing dimensions."
        ),
    )
    clarification_questions: List[str] = Field(
        default_factory=list,
        max_length=2,
        description=(
            "Up to two concise Polish questions for the user when clarification_needed is true. "
            "Must name the unresolved dimension for this question only (not a fixed checklist). "
            "Empty when clarification_needed is false."
        ),
    )
    answer_topic: AnswerTopic = Field(
        default=AnswerTopic.NONE,
        description=(
            "Composer template for the answer model when needs_rag=true and clarification_needed=false. "
            "none = no extra template; deposit_kaucja / verification / early_termination = themed answer blocks."
        ),
    )
    numeric_answer_first: bool = Field(
        default=False,
        description=(
            "True when the user expects a number, amount, or month count in the first sentence "
            "(e.g. „jaka wysokość kaucji”, „ile miesięcy”, „minimalna opłata”)."
        ),
    )


RAG_OPTIMIZER_PROMPT = """Router wyszukiwania dla asystenta Northwind Residences. Zwróć tylko pola schematu.

## Kolejność decyzji (pierwsza pasująca reguła — nie łam kolejności)

1. **Doprecyzowanie** — clarification_needed=true, needs_rag=false
2. **Smalltalk / meta / historia** — needs_rag=false, direct_mode=smalltalk
3. **Powtórzenie lub skrót** poprzedniej odpowiedzi bez nowych faktów — needs_rag=false, direct_mode=smalltalk, reuse=none
4. **Pełne RAG** — needs_rag=true, direct_mode=smalltalk

**Handbook direct (direct_mode=handbook) jest wyłączony** — nie używaj go. Pytania o Instrukcję, CRM i procesy wewnętrzne też idą przez **needs_rag=true** (wyszukiwanie w bazie; Instrukcja jest w indeksie i w anchor retrieval).
Gdy clarification_needed=true: direct_mode=smalltalk, reuse=none, answer_topic=none, numeric_answer_first=false;
optimized_query = krótkie streszczenie tematu lub puste.

---

### 1. Doprecyzowanie (clarification_needed)

Ustaw **clarification_needed=true** tylko gdy bez 1–2 krótkich pytań musiałbyś **zgadywać wymiar, który zmienia dokumenty lub reguły odpowiedzi** dla **tego** pytania.

**Zasady (nie szablon słów kluczowych):**
- W `clarification_questions` pytaj wyłącznie o **brakujące wymiary istotne dla tematu użytkownika** — sformułuj je na nowo po polsku; **nie** kopiuj gotowej listy ani stałych pytań z przykładów.
- **Nie** zakładaj, że każde szerokie pytanie o „proces” dotyczy najmu umowy — dopasuj pytania do tematu (np. zamiana mieszkania → etap/sytuacja zamiany, nie „pierwsza umowa vs przedłużenie”, o ile użytkownik o tym nie pyta).
- **Nie** doprecyzowuj, gdy w pytaniu lub historii wymiar jest już podany, albo gdy można bezpiecznie wyszukać w bazie bez zgadywania.

**Przykłady (ilustracyjne — pytania muszą pasować do tematu):**
- Szeroki proces najmu bez etapu → np. który etap (weryfikacja / umowa / wydanie) albo — jeśli dotyczy warunków — pierwsza umowa vs przedłużenie.
- „Jak wygląda wcześniejsze rozwiązanie umowy na 24 miesiące?” gdy nie wiadomo typ umowy → doprecyzuj typ umowy / ścieżkę.
- „Opisz proces zamiany mieszkania” → np. etap zamiany lub kontekst (w trakcie najmu / przy rozwiązaniu) — **nie** domyślaj się pytań o kaucję lub I vs W bez związku z pytaniem.

**Nie wymagaj doprecyzowania** gdy pytanie jest wąskie i jednoznaczne, np.:
- „Jaka wysokość kaucji przy pozytywnej weryfikacji finansowej?”
- „Na jaki okres można wynająć mieszkanie?”
- „Jak dodać klienta do procesu umowy w CRM?” (konkretny krok)

Gdy clarification_needed=true: **musisz** podać 1–2 niepuste pytania w clarification_questions (inaczej ustaw clarification_needed=false).

**Doprecyzowanie ma pierwszeństwo** przed needs_rag=true — szerokie, niejednoznaczne pytanie proceduralne nie idzie od razu w długą odpowiedź z RAG.

---

### 2. Smalltalk / meta (needs_rag=false, direct_mode=smalltalk)

Powitania, podziękowania, potwierdzenia; pytania o asystenta, datę, godzinę, źródła wiedzy asystenta („skąd to wiesz?”); kontynuacja z historii („powiedz więcej”) gdy poprzednia odpowiedź wystarczy.

---

### 3. Powtórzenie / przeformułowanie (needs_rag=false, direct_mode=smalltalk, reuse=none)

Gdy użytkownik prosi **wyłącznie** o powtórzenie, skrót lub inną formę **tej samej** poprzedniej odpowiedzi bez nowych faktów („powtórz”, „jeszcze raz krótko”, „to samo inaczej”).

**Nie myl z reuse:** reuse = to samo **tematyczne** pytanie merytoryczne przy needs_rag=true — wtedy **nie** powtarzasz odpowiedzi z historii, tylko używasz wcześniejszych fragmentów dokumentów.

---

### 4. Pełne RAG (needs_rag=true)

Umowy, opłaty, kaucja, weryfikacja finansowa, RODO, lokale, załączniki, programy rabatowe, rezerwacje, regulaminy, **kroki w CRM/Instrukcji** — zawsze wyszukiwanie w bazie (nie direct_mode=handbook).

optimized_query (po polsku):
- Dotyczy **wyłącznie bieżącego** pytania użytkownika w tej turze.
- **Nie** przenoś tematu poprzedniej tury (np. zamiana, kaucja, CRM) do optimized_query, gdy użytkownik pyta o **inny** aspekt — nawet jeśli poprzednia odpowiedź asystenta była długa.
- Historia rozmowy służy do reuse / answer_depth / clarify — **nie** do budowy optimized_query z poprzedniego tematu.
- Zachowaj nazwy własne i okresy z **tego** pytania; usuń wypełniacze.
- Nie wklejaj treści poprzedniej odpowiedzi asystenta.

reuse_previous_context (tylko gdy needs_rag=true; inaczej none):
- none — nowy temat lub świeże wyszukiwanie.
- reuse — ten sam temat co w bloku **Wcześniejsze wyszukiwanie**, te same pliki; doprecyzowanie bez nowych encji. Przy Wiek > 30 min — raczej none niż reuse.
- augment — ten sam obszar + jeden nowy aspekt; num_documents 2–4.

num_documents: 2–4 wąski fakt; 5–6 typowe; 7–8 szerokie. augment → zwykle 2–4.

answer_depth (domyślnie **concise**):
- concise — typowe pytania bez prośby o esej; wąski fakt; „krótko”.
- standard — kilka powiązanych punktów.
- detailed — wyłącznie gdy użytkownik wyraźnie prosi o pełny/przegląd („maksymalnie szczegółowo”, „wszystkie sposoby”) **oraz** clarification_needed=false **oraz** zakres jest już jasny. **Nie ustawiaj detailed** dla szerokiego „cały proces” — najpierw doprecyzuj.

retrieval_scopes i corpus_path_prefixes — patrz **mapa folderów** na końcu tej instrukcji:
- Wybierz slug(y) i opcjonalnie prefix **subfolderu** wg **aspektu pytania** (umowa vs przedłużenie vs rezerwacja vs instrukcja procedury), nie wg zgadywania kwot.
- `["all"]` tylko gdy naprawdę cross-corpus lub brak pewności **po** rozważeniu mapy; jeśli brakuje wymiaru (np. pierwsza umowa vs przedłużenie) → **clarification_needed** zamiast `all`.
- Pytania o **warunki umowne najemcy** (opłaty, kaucja, wcześniejsze rozwiązanie, przedłużenie, okres umowy) → zwykle **`1_najem_instytucjonalny`** (+ prefix z mapy: pierwsza umowa vs folder przedłużenia vs porozumienia). **`5_instrukcje`** samodzielnie tylko gdy chodzi wyłącznie o **procedurę wewnętrzną/CRM**, nie o interpretację umowy.
- Użytkownik wprost o **firmie** / **VAT** / **rezerwacji** → slug z mapy (`2_najem_firma`, `3_mieszkania_z_vatem_najem_zwyky`, `4_umowa_rezerwacyjna`).

corpus_path_prefixes: wartości `root_slug/sub_slug` z tabeli w mapie folderów; null gdy wystarczy sam slug.
corpus_file_name / corpus_source_relative_path: tylko gdy użytkownik poda dokładną nazwę/ścieżkę pliku.

---

### Szablon odpowiedzi (needs_rag=true, clarification_needed=false)

answer_topic — wskazówka **formy** odpowiedzi dla modelu (nie wpływa na routing; **bez** wpisywania kwot w routerze):
- none — CRM, RODO, ogólne procedury bez specjalnego szablonu.
- deposit_kaucja — kaucja, depozyt, progi — odpowiedź z CONTEXT.
- verification — weryfikacja tożsamości/finansowa, biuro kredytowe i rejestr długów, PESEL, Northwind, obcokrajowiec.
- early_termination — wcześniejsze rozwiązanie, porozumienie, opłaty umowne; gdy niejasna **rodzina dokumentu** → clarification zamiast zgadywania wariantu (N/W/R) w routerze.

numeric_answer_first=true gdy użytkownik oczekuje **liczby lub kwoty** w pierwszym zdaniu („jaka wysokość”, „ile miesięcy”, „minimalna opłata”). false dla pytań czysto proceduralnych."""


def _optimizer_user_style_section(user_preferences_block: str) -> str:
    """
    Extra system text when the user has /style preferences.

    Keeps needs_rag / direct_mode rules in the main prompt authoritative; this block
    only steers answer_depth (concise vs standard vs detailed) from free-text prefs.
    """
    trimmed = (user_preferences_block or "").strip()
    if not trimmed:
        return ""
    return (
        "\n\n**Preferencje stylu (/style) — wpływ na pole `answer_depth`:**\n"
        "- Poniżej wklejono zapis preferencji użytkownika (często po angielsku, np. "
        "„only short sentences”, „write me only long answers”).\n"
        "- **answer_depth:** prośby o **krótko** / **zwięźle** / **brief** / **short** / "
        "**short sentences** / „tylko krótkie zdania” ⇒ preferuj **concise**, o ile w **tym samym** "
        "pytaniu użytkownik **nie** żąda jednocześnie pełnego przeglądu („maksymalnie szczegółowo”, "
        "„wszystkie sposoby”) **oraz** clarification_needed=false.\n"
        "- **answer_depth:** wyraźna prośba o **długie** / **long** / **detailed** / **max detail** "
        "⇒ przy szerokim pytaniu preferuj **detailed** tylko gdy clarification_needed=false i zakres "
        "jest jasny; inaczej najpierw doprecyzuj.\n"
        "- **`needs_rag` i `direct_mode`:** wyznacz **wyłącznie** według reguł w głównej instrukcji powyżej "
        "(temat pytania). Same preferencje co do długości **nie** zmieniają routingu dokumentów.\n"
        "\n"
        f"{trimmed}\n"
    )


class RAGOptimizer:
    """
    Optimizes RAG retrieval using LLM-based decision making.
    
    Decides:
    - Whether to use RAG at all
    - How to rewrite the query for better retrieval
    - How many documents to retrieve (dynamic k)
    """
    
    def __init__(self, llm: ChatOpenAI):
        """
        Initialize the optimizer.
        
        Args:
            llm: ChatOpenAI instance for strategy generation
        """
        # Prefer tool/function calling over JSON-schema response_format. Some models
        # (e.g. certain gpt-5* deployments) return HTTP 400 for json_schema / strict
        # structured outputs; function calling is more widely supported.
        self.llm = llm.with_structured_output(RAGStrategy, method="function_calling")
    
    def _format_history(self, messages: list[BaseMessage], max_messages: int = 6) -> str:
        """
        Recent user + assistant turns for routing, reuse, and continuation.

        ``optimized_query`` must still derive only from the current user turn; history is for
        reuse_previous_context / answer_depth / needs_rag, not for copying into optimized_query.
        """
        if not messages:
            return "Brak historii rozmowy."
        recent = messages[-max_messages:]
        formatted: list[str] = []
        # Short snippets hide long assistant answers and make the router re-fetch on "repeat".
        user_snip_limit = 900
        assistant_snip_limit = 4500
        for msg in recent:
            if isinstance(msg, HumanMessage):
                label = "Użytkownik"
                limit = user_snip_limit
            elif isinstance(msg, AIMessage):
                label = "Asystent"
                limit = assistant_snip_limit
            else:
                continue
            content = str(msg.content)
            if len(content) > limit:
                content = content[:limit] + "..."
            formatted.append(f"{label}: {content}")
        if not formatted:
            return "Brak wcześniejszych wiadomości."
        return "\n".join(formatted)
    
    @staticmethod
    def _format_last_retrieval(last_retrieval: Optional[dict[str, Any]]) -> str:
        """
        Compact, token-frugal block describing the previous turn's retrieval.

        Returned string is empty when there is no usable cache entry — caller skips
        the section entirely so the optimizer prompt stays short on first turns.
        """
        if not last_retrieval:
            return ""
        prev_query = str(last_retrieval.get("optimized_query") or "").strip()
        sources = last_retrieval.get("sources") or []
        if not isinstance(sources, list):
            sources = []
        if not prev_query and not sources:
            return ""

        truncated_query = prev_query[:_LAST_RETRIEVAL_QUERY_CHAR_LIMIT]
        if len(prev_query) > _LAST_RETRIEVAL_QUERY_CHAR_LIMIT:
            truncated_query = truncated_query + "…"

        files: list[str] = []
        seen: set[str] = set()
        for src in sources:
            if not isinstance(src, dict):
                continue
            label = (
                str(src.get("sourceRelativePath") or "").strip()
                or str(src.get("fileName") or "").strip()
            )
            if not label or label in seen:
                continue
            seen.add(label)
            files.append(label)
            if len(files) >= _LAST_RETRIEVAL_FILES_LIMIT:
                break
        files_block = "\n".join(f"  - {path}" for path in files) if files else "  - (brak)"

        age_line = ""
        ts_raw = str(last_retrieval.get("timestamp") or "").strip()
        if ts_raw:
            try:
                ts_dt = datetime.fromisoformat(ts_raw)
                if ts_dt.tzinfo is None:
                    ts_dt = ts_dt.replace(tzinfo=timezone.utc)
                age_min = max(0.0, (datetime.now(timezone.utc) - ts_dt).total_seconds() / 60)
                age_line = f"\n- Wiek: {age_min:.0f} min temu"
            except ValueError:
                pass

        prev_line = f'- Pytanie: "{truncated_query}"' if truncated_query else "- Pytanie: (brak)"
        return (
            "**Wcześniejsze wyszukiwanie (poprzednia tura):**\n"
            f"{prev_line}\n"
            f"- Liczba pobranych fragmentów: {len(sources)}\n"
            f"- Pliki źródłowe (top {_LAST_RETRIEVAL_FILES_LIMIT}):\n"
            f"{files_block}"
            f"{age_line}"
        )

    async def optimize(
        self,
        query: str,
        history: list[BaseMessage],
        *,
        last_retrieval: Optional[dict[str, Any]] = None,
        user_preferences_block: str = "",
    ) -> RAGStrategy:
        """
        Generate an optimal RAG strategy for the given query.

        Args:
            query: The user's current question
            history: Conversation history (list of messages)
            last_retrieval: Optional cached retrieval from the previous turn
                (``optimized_query``, ``sources``, ``timestamp``). Surfaced to the
                optimizer prompt so it can pick reuse/augment/none from real data
                instead of guessing from history text alone.
            user_preferences_block: Prompt fragment from ``/style`` (same as answer model);
                biases ``answer_depth`` when non-empty.

        Returns:
            RAGStrategy with retrieval decisions
        """
        history_text = self._format_history(history)
        last_retrieval_block = self._format_last_retrieval(last_retrieval)

        prompt_sections = [f"**Historia rozmowy:**\n{history_text}"]
        if last_retrieval_block:
            prompt_sections.append(last_retrieval_block)
        prompt_sections.append(f"**Aktualne pytanie użytkownika:**\n{query}")
        prompt_sections.append("Wygeneruj optymalną strategię RAG.")

        user_prompt = "\n\n".join(prompt_sections)

        system_content = (
            RAG_OPTIMIZER_PROMPT
            + _optimizer_user_style_section(user_preferences_block)
            + get_rag_optimizer_system_prompt_appendix()
        )
        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content=user_prompt),
        ]
        
        try:
            strategy = await self.llm.ainvoke(messages)
            scope_vals = [s.value for s in strategy.retrieval_scopes]
            logger.info(
                "RAG Strategy: needs_rag=%s clarify=%s direct_mode=%s k=%s depth=%s reuse=%s "
                "topic=%s numeric_first=%s scopes=%s q=%s",
                strategy.needs_rag,
                strategy.clarification_needed,
                strategy.direct_mode.value,
                strategy.num_documents,
                strategy.answer_depth.value,
                strategy.reuse_previous_context.value,
                strategy.answer_topic.value,
                strategy.numeric_answer_first,
                scope_vals,
                strategy.optimized_query[:80],
            )
            if strategy.corpus_path_prefixes:
                logger.info("corpus_path_prefixes=%s", strategy.corpus_path_prefixes)
            if strategy.corpus_file_name:
                logger.info("corpus_file_name=%s", strategy.corpus_file_name)
            if strategy.corpus_source_relative_path:
                logger.info("corpus_source_relative_path=%s", strategy.corpus_source_relative_path)
            return strategy
        except Exception as exc:
            logger.exception("RAG optimizer structured output failed")
            api_body = getattr(exc, "body", None)
            if api_body is not None:
                logger.error("Optimizer API error body: %s", api_body)
            return RAGStrategy(
                needs_rag=True,
                direct_mode=DirectMode.SMALLTALK,
                optimized_query=query,
                num_documents=6,
                answer_depth=AnswerDepth.CONCISE,
                retrieval_scopes=[RetrievalScope.ALL],
                corpus_path_prefixes=None,
                corpus_file_name=None,
                corpus_source_relative_path=None,
                reuse_previous_context=ReusePreviousContext.NONE,
                clarification_needed=False,
                clarification_questions=[],
                answer_topic=AnswerTopic.NONE,
                numeric_answer_first=False,
            )
