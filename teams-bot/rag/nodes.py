"""Node functions for the LangGraph RAG workflow."""
import asyncio
import logging
import os
import threading
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any, AsyncIterator, Dict, Optional

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone

from config import PineconeConfig
from .handbook import handbook_direct_enabled, load_handbook_text, log_handbook_token_budget
from .answer_composer import build_topic_composer_block, format_clarification_response
from .optimizer import (
    AnswerDepth,
    DirectMode,
    RAGOptimizer,
    ReusePreviousContext,
    RetrievalTier,
    SearchFocus,
)
from .pinecone_ids import chunk_vector_id
from .prompts import ANSWER_DEPTH_INSTRUCTIONS, HANDBOOK_DIRECT_PROMPT, SYSTEM_PROMPT, WELCOME_MESSAGE
from .citations import (
    format_citations_from_display_rows,
    normalize_page_number,
    precompute_streaming_citation_map,
    should_attach_source_block,
    strip_inline_source_citation_markers,
    strip_trailing_citations_used_line,
)
from .anchor_documents import (
    NEIGHBOR_RETRIEVAL_SCORE_FACTOR,
    RETRIEVAL_SCORE_METADATA_KEY,
    anchor_chunk_filter,
    anchor_retrieval_enabled,
    anchor_retrieval_k,
    anchor_source_relative_paths,
    merge_retrieval_candidates_by_score,
    retrieval_score_from_document,
    sort_documents_by_retrieval_score,
)
from .retrieval_filter import (
    RetrievalScope,
    build_pinecone_filter_for_retrieval,
    coalesce_path_prefixes_from_state,
    coalesce_retrieval_scopes_from_state,
    merge_pinecone_filters,
    pinecone_filter_chunk_rows_only,
)

logger = logging.getLogger(__name__)

RetrievalPhaseCallback = Callable[[str, dict[str, Any]], Awaitable[None]]

# Set when ``rag_prompt | llm`` streaming completes (same asyncio task as the Teams turn).
_answer_stream_finish_reason: ContextVar[Optional[str]] = ContextVar(
    "_answer_stream_finish_reason", default=None
)


def consume_answer_stream_finish_reason() -> Optional[str]:
    """Return last streamed completion ``finish_reason`` and clear (one read per turn)."""
    value = _answer_stream_finish_reason.get()
    _answer_stream_finish_reason.set(None)
    return value


def _message_chunk_text_delta(chunk: Any) -> str:
    """Extract incremental text from a streamed chat model chunk."""
    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def _finish_reason_from_message_chunk(chunk: Any) -> Optional[str]:
    meta = getattr(chunk, "response_metadata", None)
    if not isinstance(meta, dict):
        return None
    finish = meta.get("finish_reason")
    if isinstance(finish, str):
        return finish
    generation_info = meta.get("generation_info")
    if isinstance(generation_info, dict):
        nested = generation_info.get("finish_reason")
        if isinstance(nested, str):
            return nested
    return None

# Default cap for formatted RAG context (~12k tokens depending on language).
# gpt-5-mini leaves ample window for system prompt + history; override via ``MAX_RAG_CONTEXT_CHARS``.
_DEFAULT_MAX_RAG_CONTEXT_CHARS = 48_000


def _summary_retrieval_enabled_from_env() -> bool:
    """When false, skip summary-first stage (use chunk-only dense search). Default off."""
    raw = os.environ.get("SUMMARY_RETRIEVAL_ENABLED", "0").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _neighbor_expansion_enabled_from_env() -> bool:
    """When true, fetch chunkIndex±1 neighbors after primary retrieval. Default off."""
    raw = os.environ.get("RAG_NEIGHBOR_EXPANSION_ENABLED", "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


# System prompt for direct responses (no RAG context)
DIRECT_RESPONSE_PROMPT = """Jesteś Asystentem Northwind Residences - przyjaznym pomocnikiem dla pracowników firmy. Odpowiadaj po polsku.

Właśnie prowadzisz swobodną rozmowę - odpowiadasz na powitania, podziękowania lub pytania kontekstowe.

**Bez zbędnych potwierdzeń (dowolny język):** nie zaczynaj od „potwierdzam”, „thanks”, „дякую” itp. — od razu merytoria.
**Pogrubienia:** używaj `**pogrubienia**` dla ważnych pojęć i dat, gdy to pomaga.

**Preferencje osobiste (/style):** gdy blok poniżej nie jest pusty — traktuj go jak **twardy** wymóg stylu i długości dla tej odpowiedzi (także intencje po angielsku, np. „only short sentences”); **pierwszeństwo** nad zachętami do rozbudowanych odpowiedzi poniżej.

{user_preferences_block}

**Wskazówki:**
- Bądź uprzejmy i naturalny
- Jeśli użytkownik kontynuuje poprzedni temat, nawiązuj do historii rozmowy
- Jeśli pyta o procedury, dokumenty lub szczegóły firmowe - zachęć do zadania konkretnego pytania, a przeszukam dokumentację
- Nie wymyślaj informacji o firmie - możesz tylko szukać w dokumentach

Historia rozmowy:
{history}
"""


def _document_header_lines(metadata: dict) -> str:
    file_name = metadata.get("fileName", "Dokument")
    page_display = normalize_page_number(metadata.get("pageNumber"))
    section = metadata.get("sectionTitle", "")
    rel_path = metadata.get("sourceRelativePath", "")
    section_path = metadata.get("sectionPath", "")

    header_parts = [f"Dokument: {file_name}"]
    if rel_path:
        header_parts.append(f"Ścieżka: {rel_path}")
    if page_display is not None:
        header_parts.append(f"Strona: {page_display}")
    if section_path:
        header_parts.append(f"Ścieżka sekcji: {section_path}")
    if section:
        header_parts.append(f"Sekcja: {section}")
    return " | ".join(header_parts)


def format_docs(docs: list[Document]) -> str:
    """Format retrieved documents as context string."""
    formatted = []
    for doc in docs:
        header = _document_header_lines(doc.metadata)
        formatted.append(f"---\n{header}\n{doc.page_content}\n---")
    return "\n\n".join(formatted)


def _merge_documents_unique_order(first: list[Document], second: list[Document]) -> list[Document]:
    """Concatenate ``first`` then ``second``, dropping duplicate (docId, chunkIndex) rows."""
    seen: set[tuple[Any, Any]] = set()
    merged: list[Document] = []
    for doc in first + second:
        meta = doc.metadata
        key = (meta.get("docId"), meta.get("chunkIndex"))
        if key[0] is None or key[1] is None:
            merged.append(doc)
            continue
        if key in seen:
            continue
        seen.add(key)
        merged.append(doc)
    return merged


def postprocess_rag_answer_text_with_precomputed_map(
    raw_response: str,
    display_rows: list[dict],
) -> tuple[str, list[dict], str, bool]:
    """Post-process the RAG answer for Teams streaming and non-streaming callers.

    Strips a trailing legacy ``CITATIONS_USED:`` line and any stray ``[Źródło N]`` /
    ``[Citation N]`` the model might still emit. **Źródła** are built from
    ``display_rows`` (one row per retrieved document from
    :func:`citations.precompute_streaming_citation_map`) whenever
    :func:`citations.should_attach_source_block` allows attaching sources — no inline
    citation tags are required in the model output.

    The streamed visible prefix uses :func:`citations.streaming_safe_answer_visible_text`,
    which matches the same ``strip_trailing_citations_used_line`` behaviour, so the
    cumulative stream stays a prefix of the final body.
    """
    display = strip_trailing_citations_used_line(raw_response)
    display = strip_inline_source_citation_markers(display)
    picked_sources: list[dict] = []
    citations = ""
    attach_sources_block = False
    if display_rows and should_attach_source_block(display):
        attach_sources_block = True
        picked_sources = list(display_rows)
        citations = format_citations_from_display_rows(display_rows)
    return display, picked_sources, citations, attach_sources_block


def postprocess_rag_answer_text(raw_response: str, sources: list[dict]) -> tuple[str, list[dict], str, bool]:
    """Strip legacy tails; build **Źródła** from retrieved ``sources`` when attachment is allowed."""
    display_rows: list[dict] = []
    if sources:
        _ctx_map, display_rows, _max_display = precompute_streaming_citation_map(sources)
    return postprocess_rag_answer_text_with_precomputed_map(raw_response, display_rows)


def format_docs_numbered(docs: list[Document]) -> str:
    """Format retrieved chunks as numbered CONTEXT fragments (no ``[Źródło N]`` tags)."""
    parts: list[str] = []
    for index, doc in enumerate(docs, start=1):
        header = _document_header_lines(doc.metadata)
        score = doc.metadata.get(RETRIEVAL_SCORE_METADATA_KEY)
        score_suffix = ""
        if score is not None:
            score_suffix = (
                f" | Trafność wyszukiwania: {float(score):.3f} "
                f"(wyższa = bliżej bieżącego pytania)"
            )
        parts.append(
            f"**Fragment {index}**{score_suffix}\n---\n{header}\n{doc.page_content}\n---"
        )
    return "\n\n".join(parts)


def extract_sources(docs: list[Document]) -> list[dict]:
    """Extract source metadata from documents for citations."""
    return [
        {
            "fileName": doc.metadata.get("fileName", ""),
            "docId": doc.metadata.get("docId"),
            "pageNumber": doc.metadata.get("pageNumber"),
            "sectionTitle": doc.metadata.get("sectionTitle"),
            "sectionPath": doc.metadata.get("sectionPath"),
            "sourceRelativePath": doc.metadata.get("sourceRelativePath"),
            "chunkIndex": doc.metadata.get("chunkIndex"),
            "blockStartIndex": doc.metadata.get("blockStartIndex"),
            "blockEndIndex": doc.metadata.get("blockEndIndex"),
            "sharepointUrl": doc.metadata.get("sharepointUrl"),
            "highlightPhrase": doc.metadata.get("highlightPhrase"),
            "retrievalScore": doc.metadata.get(RETRIEVAL_SCORE_METADATA_KEY),
        }
        for doc in docs
    ]


def format_history_for_prompt(messages: list) -> str:
    """Format message history for inclusion in prompts."""
    if not messages:
        return "Brak historii."
    
    formatted = []
    for msg in messages[-6:]:  # Last 6 messages
        if isinstance(msg, HumanMessage):
            formatted.append(f"Użytkownik: {msg.content}")
        elif isinstance(msg, AIMessage):
            # Truncate long responses
            content = msg.content[:300] + "..." if len(msg.content) > 300 else msg.content
            formatted.append(f"Asystent: {content}")
    
    return "\n".join(formatted)


_GREETING_ACK_EXACT: frozenset[str] = frozenset(
    {
        "cześć",
        "czesc",
        "czescz",
        "czesz",
        "czezcz",
        "czeszc",
        "hej",
        "hejo",
        "siema",
        "elo",
        "witaj",
        "witam",
        "hi",
        "hello",
        "hey",
        "yo",
        "ahoj",
        "dzień dobry",
        "dzien dobry",
        "dzięki",
        "dzieki",
        "dziękuję",
        "dziekuje",
        "thanks",
        "thx",
        "ok",
        "okay",
        "pa",
        "nara",
    }
)


def is_short_greeting_or_acknowledgment(user_message: str) -> bool:
    """
    Short greetings / thanks / acks — including common typos (e.g. ``czescz``).

    Used so trivial turns are not routed to handbook or Pinecone.
    """
    raw = (user_message or "").strip()
    if not raw:
        return False
    collapsed = " ".join(raw.lower().split())
    collapsed = collapsed.rstrip("!?.,…").strip()
    if len(collapsed) > 40:
        return False
    if collapsed in _GREETING_ACK_EXACT:
        return True
    letters_only = "".join(ch for ch in collapsed if ch.isalpha())
    if not letters_only or len(letters_only) > 9:
        return False
    allowed_letters = frozenset("cześćśsczć")
    if letters_only.startswith("cz") and set(letters_only) <= allowed_letters:
        return True
    return False


class RAGNodes:
    """
    Node implementations for the LangGraph RAG workflow.
    
    Nodes:
    - optimize: LLM decides RAG strategy (whether to search, query optimization, k value)
    - retrieve: Fetch documents from Pinecone with dynamic k
    - respond_with_rag: Generate response using retrieved context
    - respond_direct: Generate response without RAG (greetings, follow-ups)
    """
    
    def __init__(
        self,
        llm: ChatOpenAI,
        optimizer_llm: ChatOpenAI,
        embeddings: OpenAIEmbeddings,
        vectorstore: PineconeVectorStore,
        pinecone_config: PineconeConfig,
    ):
        """
        Initialize the RAG nodes.

        Args:
            llm: ChatOpenAI for answer generation (e.g. gpt-5-mini)
            optimizer_llm: ChatOpenAI for retrieval strategy (e.g. gpt-5-nano)
            embeddings: OpenAI embeddings for retrieval
            vectorstore: Pinecone vector store
            pinecone_config: API key, index name, namespace for fetch-by-id
        """
        self.llm = llm
        self.embeddings = embeddings
        self.vectorstore = vectorstore
        self.optimizer = RAGOptimizer(optimizer_llm)
        self._pinecone_api_key = pinecone_config.api_key
        self._pinecone_index_name = pinecone_config.index_name
        self._pinecone_namespace = pinecone_config.namespace
        self._retrieval_phase_callback: Optional[RetrievalPhaseCallback] = None
        # ``langchain_pinecone`` async search uses ``async with`` on a shared ``IndexAsyncio``.
        # Concurrent ``asyncio.gather`` (anchor + primary) must not run two queries at once or
        # aiohttp raises ``RuntimeError: Session is closed`` when one context exits (prod 2026-04).
        self._vectorstore_async_lock: Optional[asyncio.Lock] = None
        self._vectorstore_async_lock_guard = threading.Lock()

        raw_max = os.environ.get("MAX_RAG_CONTEXT_CHARS", "").strip()
        self._max_rag_context_chars = (
            int(raw_max) if raw_max else _DEFAULT_MAX_RAG_CONTEXT_CHARS
        )

        pinecone_client = Pinecone(api_key=self._pinecone_api_key)
        self._pinecone_index = pinecone_client.Index(self._pinecone_index_name)

        # RAG prompt template (history = prior turns; current question in final human message)
        self.rag_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{question}"),
            ]
        )
        
        # Direct response prompt template
        self.direct_prompt = ChatPromptTemplate.from_messages([
            ("system", DIRECT_RESPONSE_PROMPT),
            ("human", "{question}"),
        ])
        self.handbook_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", HANDBOOK_DIRECT_PROMPT),
                ("human", "{question}"),
            ]
        )
        log_handbook_token_budget()

    def set_retrieval_phase_callback(self, cb: Optional[RetrievalPhaseCallback]) -> None:
        self._retrieval_phase_callback = cb

    def _get_vectorstore_async_lock(self) -> asyncio.Lock:
        """Lazily create lock on first async retrieval (sync prewarm may construct RAGGraph with no loop)."""
        with self._vectorstore_async_lock_guard:
            if self._vectorstore_async_lock is None:
                self._vectorstore_async_lock = asyncio.Lock()
            return self._vectorstore_async_lock

    async def _notify_retrieval_phase(self, phase: str, info: dict[str, Any]) -> None:
        callback = self._retrieval_phase_callback
        if callback is not None:
            await callback(phase, info)
    
    async def optimize(self, state: dict) -> dict:
        """
        LLM decides RAG strategy based on query and history.
        
        Input state:
            - messages: list of BaseMessage
            
        Output state additions:
            - needs_rag: bool
            - optimized_query: str
            - num_documents: int
            - search_focus: str
        """
        messages = state.get("messages", [])
        
        # Get the last user message
        last_message = messages[-1] if messages else None
        if not last_message or not isinstance(last_message, HumanMessage):
            logger.warning("No user message found in state")
            return {
                "needs_rag": False,
                "optimized_query": "",
                "num_documents": 0,
                "search_focus": SearchFocus.NONE.value,
                "retrieval_scopes": [RetrievalScope.ALL.value],
                "retrieval_tier": RetrievalTier.CHUNKS_ONLY.value,
                "optimizer_reasoning": "",
                "corpus_path_prefixes": [],
                "corpus_file_name": "",
                "corpus_source_relative_path": "",
                "answer_depth": AnswerDepth.CONCISE.value,
                "reuse_previous_context": ReusePreviousContext.NONE.value,
                "direct_mode": DirectMode.SMALLTALK.value,
                "clarification_needed": False,
                "clarification_questions": [],
                "answer_topic": "none",
                "numeric_answer_first": False,
            }
        
        query = last_message.content
        history = messages[:-1]  # All messages except the current one

        # Pass the cached previous-turn retrieval (if any) to the optimizer so it can
        # pick reuse / augment / none informed by the actual cached scope + sources +
        # previous optimized_query, instead of guessing from conversation text alone.
        cached_entry = state.get("cached_rag_entry") or None
        strategy = await self.optimizer.optimize(
            query,
            history,
            last_retrieval=cached_entry,
            user_preferences_block=str(state.get("user_preferences_block") or ""),
        )

        clarification_questions_out = [
            str(q).strip() for q in (strategy.clarification_questions or []) if str(q).strip()
        ][:2]
        clarification_needed_out = bool(
            strategy.clarification_needed and clarification_questions_out
        )
        user_query_stripped = str(query).strip()

        needs_rag_out = strategy.needs_rag
        direct_mode_out = strategy.direct_mode

        answer_topic_out = strategy.answer_topic.value
        numeric_answer_first_out = strategy.numeric_answer_first

        if clarification_needed_out:
            needs_rag_out = False
            direct_mode_out = DirectMode.SMALLTALK
            answer_topic_out = "none"
            numeric_answer_first_out = False
        elif is_short_greeting_or_acknowledgment(user_query_stripped):
            needs_rag_out = False
            direct_mode_out = DirectMode.SMALLTALK
        elif direct_mode_out == DirectMode.HANDBOOK and handbook_direct_enabled():
            try:
                load_handbook_text()
                needs_rag_out = False
                direct_mode_out = DirectMode.HANDBOOK
            except FileNotFoundError:
                logger.warning("Handbook corpus missing; coercing to RAG for this turn.")
                needs_rag_out = True
                direct_mode_out = DirectMode.SMALLTALK
        elif direct_mode_out == DirectMode.HANDBOOK and not handbook_direct_enabled():
            logger.info("Handbook direct disabled by env; coercing to RAG for this turn.")
            needs_rag_out = True
            direct_mode_out = DirectMode.SMALLTALK
        elif needs_rag_out:
            direct_mode_out = DirectMode.SMALLTALK

        optimized_query_out = strategy.optimized_query
        if needs_rag_out and not strategy.needs_rag:
            user_query = str(query).strip()
            optimized_query_out = user_query or strategy.optimized_query

        cpp_list = strategy.corpus_path_prefixes or []
        cfn = strategy.corpus_file_name
        csrp = strategy.corpus_source_relative_path
        scope_values = [scope.value for scope in strategy.retrieval_scopes]
        reuse_pc = (
            strategy.reuse_previous_context.value
            if needs_rag_out and not clarification_needed_out
            else ReusePreviousContext.NONE.value
        )
        # ``search_focus`` and ``retrieval_tier`` were dropped from the optimizer schema
        # to cut output tokens (and reasoning latency on gpt-5-* models). They are still
        # surfaced in audit/state with stable defaults: retrieval_tier is overridden by
        # SUMMARY_RETRIEVAL_ENABLED in retrieve(); search_focus is audit-only.
        return {
            "needs_rag": needs_rag_out,
            "direct_mode": direct_mode_out.value,
            "optimized_query": optimized_query_out,
            "num_documents": strategy.num_documents,
            "search_focus": SearchFocus.SPECIFIC.value,
            "retrieval_scopes": scope_values,
            "retrieval_tier": RetrievalTier.CHUNKS_ONLY.value,
            "optimizer_reasoning": "",
            "corpus_path_prefixes": list(cpp_list),
            "corpus_file_name": cfn if cfn else "",
            "corpus_source_relative_path": csrp if csrp else "",
            "answer_depth": strategy.answer_depth.value,
            "reuse_previous_context": reuse_pc,
            "clarification_needed": clarification_needed_out,
            "clarification_questions": clarification_questions_out,
            "answer_topic": answer_topic_out,
            "numeric_answer_first": numeric_answer_first_out,
        }

    async def respond_clarify(self, state: dict) -> dict:
        """
        Return clarifying questions without retrieval or answer LLM (B4 / A9 / A13 gate).
        """
        questions = state.get("clarification_questions") or []
        if not isinstance(questions, list):
            questions = []
        response = format_clarification_response(questions)
        return {
            "response": response,
            "citations": "",
            "attach_sources_block": False,
        }

    def _cap_documents_by_context_size(self, docs: list[Document]) -> list[Document]:
        """Drop tail documents if formatted context would exceed the configured char cap."""
        kept: list[Document] = []
        total = 0
        for doc in docs:
            block = format_docs([doc])
            if total + len(block) > self._max_rag_context_chars and kept:
                break
            kept.append(doc)
            total += len(block)
        return kept

    async def _pinecone_fetch_by_ids(self, vector_ids: list[str]) -> dict[str, Document]:
        """Fetch vectors by id; returns map id -> Document (chunk rows only)."""

        def _sync() -> dict[str, Document]:
            if not vector_ids:
                return {}
            res = self._pinecone_index.fetch(
                ids=vector_ids,
                namespace=self._pinecone_namespace,
            )
            out: dict[str, Document] = {}
            if not res or not getattr(res, "vectors", None):
                return out
            for vid, row in res.vectors.items():
                meta = dict(row.metadata) if row.metadata else {}
                if meta.get("summaries") is True:
                    continue
                text = meta.get("text") or ""
                out[str(vid)] = Document(page_content=text, metadata=meta)
            return out

        return await asyncio.to_thread(_sync)

    async def _chunks_from_summary_hits(self, summary_docs: list[Document]) -> list[Document]:
        """Load chunk rows covered by summary span metadata (chunkIndexStart..chunkIndexEnd)."""
        ordered_ids: list[str] = []
        seen: set[str] = set()
        for sdoc in summary_docs:
            meta = sdoc.metadata
            doc_id = meta.get("docId")
            start = meta.get("chunkIndexStart")
            end = meta.get("chunkIndexEnd")
            if doc_id is None or start is None or end is None:
                logger.warning("Summary vector missing docId or chunk span bounds: keys=%s", list(meta.keys()))
                continue
            start_i = int(start)
            end_i = int(end)
            if end_i < start_i:
                logger.warning("Invalid span %s..%s for docId=%s", start_i, end_i, doc_id)
                continue
            for ci in range(start_i, end_i + 1):
                vid = chunk_vector_id(str(doc_id), ci)
                if vid not in seen:
                    seen.add(vid)
                    ordered_ids.append(vid)

        if not ordered_ids:
            return []

        id_to_doc = await self._pinecone_fetch_by_ids(ordered_ids)
        return [id_to_doc[i] for i in ordered_ids if i in id_to_doc]

    @staticmethod
    def _documents_with_retrieval_scores(
        pairs: list[tuple[Document, float]],
    ) -> list[Document]:
        docs: list[Document] = []
        for doc, score in pairs:
            meta = dict(doc.metadata)
            meta[RETRIEVAL_SCORE_METADATA_KEY] = float(score)
            docs.append(Document(page_content=doc.page_content, metadata=meta))
        return docs

    async def _retrieve_chunks_direct(
        self,
        query: str,
        num_docs: int,
        scope_filter: Optional[Dict[str, Any]],
        *,
        use_chunk_row_filter: bool,
    ) -> list[Document]:
        chunk_filter = (
            pinecone_filter_chunk_rows_only(scope_filter)
            if use_chunk_row_filter
            else scope_filter
        )
        k = int(num_docs)
        async with self._get_vectorstore_async_lock():
            if chunk_filter is not None:
                pairs = await self.vectorstore.asimilarity_search_with_score(
                    query, k=k, filter=chunk_filter
                )
            else:
                pairs = await self.vectorstore.asimilarity_search_with_score(query, k=k)
        return self._documents_with_retrieval_scores(pairs)

    async def _expand_neighbors(self, primary_docs: list[Document]) -> list[Document]:
        """Append chunkIndex +/- 1 neighbors for each primary hit (same docId)."""
        if not primary_docs:
            return []

        ordered_primary: list[Document] = []
        seen: set[str] = set()
        for doc in primary_docs:
            meta = doc.metadata
            doc_id = meta.get("docId")
            chunk_idx = meta.get("chunkIndex")
            if doc_id is None or chunk_idx is None:
                ordered_primary.append(doc)
                continue
            vid = chunk_vector_id(str(doc_id), int(chunk_idx))
            if vid not in seen:
                seen.add(vid)
                ordered_primary.append(doc)

        neighbor_ids: list[str] = []
        neighbor_parent_score: dict[str, float] = {}
        for doc in primary_docs:
            meta = doc.metadata
            doc_id = meta.get("docId")
            chunk_idx = meta.get("chunkIndex")
            if doc_id is None or chunk_idx is None:
                continue
            parent_score = retrieval_score_from_document(doc)
            ci = int(chunk_idx)
            for delta in (-1, 1):
                nid = chunk_vector_id(str(doc_id), ci + delta)
                if nid not in seen:
                    seen.add(nid)
                    neighbor_ids.append(nid)
                    if parent_score >= 0:
                        neighbor_parent_score[nid] = parent_score * NEIGHBOR_RETRIEVAL_SCORE_FACTOR

        neighbor_map = await self._pinecone_fetch_by_ids(neighbor_ids)
        neighbor_docs: list[Document] = []
        for nid in neighbor_ids:
            row = neighbor_map.get(nid)
            if row is None:
                continue
            parent_score = neighbor_parent_score.get(nid)
            if parent_score is not None:
                meta = dict(row.metadata)
                meta[RETRIEVAL_SCORE_METADATA_KEY] = parent_score
                row = Document(page_content=row.page_content, metadata=meta)
            neighbor_docs.append(row)
        return ordered_primary + neighbor_docs

    async def _retrieve_primary_docs(
        self,
        *,
        query: str,
        num_docs: int,
        tier: RetrievalTier,
        pinecone_filter: Optional[Dict[str, Any]],
        summary_k: int,
    ) -> tuple[list[Document], bool]:
        """Scoped (or unscoped fallback) primary chunk retrieval; no anchor merge."""
        docs: list[Document] = []
        retrieval_fallback_unfiltered = False
        if tier == RetrievalTier.SUMMARY_THEN_CHUNKS:
            summary_filter = merge_pinecone_filters(pinecone_filter, {"summaries": True})
            retriever = self.vectorstore.as_retriever(
                search_kwargs={"k": summary_k, "filter": summary_filter}
            )
            async with self._get_vectorstore_async_lock():
                summary_docs = await retriever.ainvoke(query)
            if summary_docs:
                chunk_docs = await self._chunks_from_summary_hits(summary_docs)
                if chunk_docs:
                    docs = chunk_docs
                    logger.info(
                        "Summary-first path: %s summaries -> %s chunk rows",
                        len(summary_docs),
                        len(chunk_docs),
                    )
            if not docs:
                docs = await self._retrieve_chunks_direct(
                    query, num_docs, pinecone_filter, use_chunk_row_filter=True
                )
        else:
            docs = await self._retrieve_chunks_direct(
                query, num_docs, pinecone_filter, use_chunk_row_filter=True
            )

        if not docs and pinecone_filter is not None:
            retrieval_fallback_unfiltered = True
            logger.warning(
                "Scoped chunk retrieval returned 0 documents; retrying without corpusTopic filter"
            )
            await self._notify_retrieval_phase("scoped_fallback", {})
            docs = await self._retrieve_chunks_direct(
                query, num_docs, None, use_chunk_row_filter=True
            )
        return docs, retrieval_fallback_unfiltered

    async def retrieve(self, state: dict) -> dict:
        """
        Retrieve from Pinecone (summary-first when tier allows), optional neighbor expansion, cap context size.

        Input state:
            - optimized_query: str
            - num_documents: int
            - retrieval_tier: str
            - reuse_previous_context: none | reuse | augment
            - cached_rag_entry: optional dict from ``ContextCache.get_latest``
        """
        num_docs_raw = state.get("num_documents", 12)
        num_docs = int(num_docs_raw)
        tier_raw = state.get("retrieval_tier", RetrievalTier.SUMMARY_THEN_CHUNKS.value)
        try:
            tier = RetrievalTier(tier_raw)
        except ValueError:
            logger.warning("Unknown retrieval_tier %r; using summary_then_chunks", tier_raw)
            tier = RetrievalTier.SUMMARY_THEN_CHUNKS

        if not _summary_retrieval_enabled_from_env():
            tier = RetrievalTier.CHUNKS_ONLY

        reuse_mode = (state.get("reuse_previous_context") or "none").strip().lower()
        cached = state.get("cached_rag_entry")

        if reuse_mode == "reuse" and cached and str(cached.get("context_text") or "").strip():
            await self._notify_retrieval_phase("cache_hit", {"mode": "reuse"})
            await self._notify_retrieval_phase(
                "context_ready",
                {
                    "chunk_count": len(cached.get("sources") or []),
                    "fallback": False,
                    "cache": True,
                },
            )
            return {
                "context": str(cached["context_text"]),
                "sources": list(cached["sources"]),
                "retrieved_docs": [],
                "retrieval_fallback_unfiltered": False,
            }

        query = str(state.get("optimized_query", "") or "").strip()
        if not query:
            messages = state.get("messages") or []
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage):
                    query = str(msg.content).strip()
                    break
        if not query:
            logger.warning("No query for retrieval")
            return {
                "context": "",
                "sources": [],
                "retrieved_docs": [],
                "retrieval_fallback_unfiltered": False,
            }

        original_num_docs = int(num_docs)
        augment_active = (
            reuse_mode == "augment"
            and cached is not None
            and bool(cached.get("chunk_ids"))
        )
        cached_docs_pre: list[Document] = []
        if augment_active:
            chunk_id_list = [str(chunk_id) for chunk_id in cached["chunk_ids"]]
            id_map = await self._pinecone_fetch_by_ids(chunk_id_list)
            for chunk_id in chunk_id_list:
                row = id_map.get(chunk_id)
                if row is not None:
                    cached_docs_pre.append(row)
            if cached_docs_pre:
                num_docs = max(2, min(original_num_docs, 4))
            else:
                augment_active = False
                num_docs = original_num_docs

        await self._notify_retrieval_phase(
            "vector_search",
            {"tier": tier.value, "augment": augment_active},
        )

        scopes_resolved = coalesce_retrieval_scopes_from_state(state)
        prefix_list = coalesce_path_prefixes_from_state(state)
        file_raw = (state.get("corpus_file_name") or "").strip()
        rel_raw = (state.get("corpus_source_relative_path") or "").strip()
        pinecone_filter = build_pinecone_filter_for_retrieval(
            scopes_resolved,
            corpus_path_prefixes=prefix_list,
            corpus_file_name=file_raw,
            corpus_source_relative_path=rel_raw,
        )
        scope_raw = [s.value for s in scopes_resolved]
        logger.info(
            "Retrieving up to %s chunk-rows tier=%s for: %s... scopes=%s path_prefixes=%s "
            "file=%s rel_path=%s",
            num_docs,
            tier.value,
            query[:50],
            scope_raw,
            prefix_list or "(none)",
            file_raw or "(none)",
            rel_raw or "(none)",
        )

        summary_k = min(24, max(int(num_docs), 4))
        anchor_paths = anchor_source_relative_paths() if anchor_retrieval_enabled() else []
        anchor_filter = anchor_chunk_filter(anchor_paths) if anchor_paths else None

        if anchor_filter is not None:
            anchor_k = anchor_retrieval_k()
            logger.info(
                "Parallel anchor retrieval k=%s paths=%s",
                anchor_k,
                anchor_paths,
            )
            primary_task = self._retrieve_primary_docs(
                query=query,
                num_docs=num_docs,
                tier=tier,
                pinecone_filter=pinecone_filter,
                summary_k=summary_k,
            )
            anchor_task = self._retrieve_chunks_direct(
                query,
                anchor_k,
                anchor_filter,
                use_chunk_row_filter=False,
            )
            primary_result, anchor_out = await asyncio.gather(
                primary_task,
                anchor_task,
                return_exceptions=True,
            )
            if isinstance(primary_result, Exception):
                raise primary_result
            docs, retrieval_fallback_unfiltered = primary_result
            anchor_docs: list[Document] = []
            if isinstance(anchor_out, Exception):
                logger.exception(
                    "Anchor retrieval failed (continuing with primary only): %s",
                    anchor_out,
                )
            else:
                anchor_docs = anchor_out
            if anchor_docs:
                before = len(docs)
                docs = merge_retrieval_candidates_by_score(anchor_docs, docs)
                logger.info(
                    "Merged anchor+primary by score: anchor=%s primary=%s merged=%s top_score=%s",
                    len(anchor_docs),
                    before,
                    len(docs),
                    retrieval_score_from_document(docs[0]) if docs else None,
                )
        else:
            docs, retrieval_fallback_unfiltered = await self._retrieve_primary_docs(
                query=query,
                num_docs=num_docs,
                tier=tier,
                pinecone_filter=pinecone_filter,
                summary_k=summary_k,
            )

        if augment_active and cached_docs_pre:
            before_merge = len(docs)
            docs = _merge_documents_unique_order(cached_docs_pre, docs)
            logger.info(
                "Augment merge: cached=%s primary=%s merged=%s",
                len(cached_docs_pre),
                before_merge,
                len(docs),
            )
            await self._notify_retrieval_phase(
                "cache_augment",
                {"cached_rows": len(cached_docs_pre), "merged_rows": len(docs)},
            )

        if not docs:
            logger.warning(
                "Pinecone returned 0 documents for query (check namespace matches ingestion, "
                "and index name matches PINECONE_INDEX_NAME / PINECONE_INDEX)"
            )
        else:
            neighbor_expansion = _neighbor_expansion_enabled_from_env()
            if neighbor_expansion:
                await self._notify_retrieval_phase(
                    "neighbor_expansion",
                    {"primary_rows": len(docs)},
                )
                expanded = await self._expand_neighbors(docs)
            else:
                expanded = docs
            scored = sort_documents_by_retrieval_score(expanded)
            capped = self._cap_documents_by_context_size(scored)
            logger.info(
                "Retrieved %s rows -> %s after score sort + context cap (neighbor_expansion=%s)",
                len(docs),
                len(capped),
                neighbor_expansion,
            )
            docs = capped

        await self._notify_retrieval_phase(
            "context_ready",
            {"chunk_count": len(docs), "fallback": retrieval_fallback_unfiltered},
        )

        out: dict[str, Any] = {
            "context": format_docs_numbered(docs),
            "sources": extract_sources(docs),
            "retrieved_docs": docs,
            "retrieval_fallback_unfiltered": retrieval_fallback_unfiltered,
        }
        if not docs:
            out["needs_rag"] = False
            out["direct_mode"] = DirectMode.SMALLTALK.value
        return out
    
    async def respond_with_rag(self, state: dict) -> dict:
        """
        Generate response using retrieved context.
        
        Input state:
            - messages: list of BaseMessage
            - context: str
            - sources: list[dict]
            
        Output state additions:
            - response: str (answer body; legacy ``[Źródło N]`` stripped if present)
            - citations: str (formatted **Źródła** markdown from retrieval)
            - sources: list of citation rows attached when ``attach_sources_block``
            - attach_sources_block: whether Teams should append **Źródła** (retrieval + ``should_attach_source_block``)
        """
        messages = state.get("messages", [])
        context = state.get("context", "")
        sources = state.get("sources", [])
        
        # Current turn is always last message (history + this HumanMessage from inner pipeline).
        question = ""
        if messages and isinstance(messages[-1], HumanMessage):
            question = str(messages[-1].content)
        else:
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage):
                    question = str(msg.content)
                    break
        
        if not question:
            return {"response": "Nie rozumiem pytania.", "citations": ""}

        depth_raw = (state.get("answer_depth") or AnswerDepth.STANDARD.value).strip().lower()
        depth_key = depth_raw if depth_raw in ANSWER_DEPTH_INSTRUCTIONS else AnswerDepth.STANDARD.value
        answer_depth_block = ANSWER_DEPTH_INSTRUCTIONS[depth_key]
        answer_topic = str(state.get("answer_topic") or "none")
        numeric_answer_first = bool(state.get("numeric_answer_first"))
        topic_composer_block = build_topic_composer_block(answer_topic, numeric_answer_first)

        prior_messages: list[BaseMessage] = messages[:-1] if messages else []
        history_slice = prior_messages[-12:] if prior_messages else []

        chain = self.rag_prompt | self.llm | StrOutputParser()

        response = await chain.ainvoke(
            {
                "context": context,
                "question": question,
                "answer_depth_block": answer_depth_block,
                "topic_composer_block": topic_composer_block,
                "history": history_slice,
                "user_preferences_block": str(state.get("user_preferences_block") or ""),
            }
        )

        display, picked, citations, attach_sources_block = postprocess_rag_answer_text(
            response, sources
        )

        return {
            "response": display,
            "citations": citations,
            "sources": picked,
            "attach_sources_block": attach_sources_block,
        }
    
    async def respond_direct(self, state: dict) -> dict:
        """
        Generate response without RAG (for greetings, meta-questions, follow-ups).
        
        Input state:
            - messages: list of BaseMessage
            
        Output state additions:
            - response: str
            - citations: str (empty)
        """
        messages = state.get("messages", [])
        
        question = ""
        if messages and isinstance(messages[-1], HumanMessage):
            question = str(messages[-1].content)
        else:
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage):
                    question = str(msg.content)
                    break
        
        if not question:
            return {"response": WELCOME_MESSAGE, "citations": ""}
        
        # Check for greetings
        greetings = ["cześć", "czesc", "hej", "hi", "hello", "dzień dobry", "dzien dobry", "witam"]
        if question.lower().strip() in greetings:
            return {"response": WELCOME_MESSAGE, "citations": ""}
        
        # Format history for context
        history_text = format_history_for_prompt(messages[:-1])

        direct_mode_raw = str(state.get("direct_mode") or DirectMode.SMALLTALK.value).strip().lower()
        use_handbook = direct_mode_raw == DirectMode.HANDBOOK.value and handbook_direct_enabled()
        if use_handbook:
            try:
                handbook_blob = load_handbook_text()
            except FileNotFoundError:
                logger.warning("Handbook corpus missing at respond_direct; using smalltalk prompt.")
                use_handbook = False
                handbook_blob = ""

        prefs_block = str(state.get("user_preferences_block") or "")
        if use_handbook and handbook_blob:
            chain = self.handbook_prompt | self.llm | StrOutputParser()
            response = await chain.ainvoke(
                {
                    "history": history_text,
                    "handbook_context": handbook_blob,
                    "question": question,
                    "user_preferences_block": prefs_block,
                }
            )
        else:
            chain = self.direct_prompt | self.llm | StrOutputParser()
            response = await chain.ainvoke(
                {
                    "history": history_text,
                    "question": question,
                    "user_preferences_block": prefs_block,
                }
            )

        return {
            "response": response,
            "citations": "",
        }
    
    async def astream_respond_with_rag(
        self,
        context: str,
        question: str,
        history_messages: list[BaseMessage],
        answer_depth_block: str,
        *,
        user_preferences_block: str = "",
        topic_composer_block: str = "",
    ) -> AsyncIterator[str]:
        """
        Stream raw model chunks for the RAG path (caller may hide a fully-formed legacy machine line).

        Uses ``rag_prompt | llm`` (not ``StrOutputParser``) so the last chunk's
        ``response_metadata.finish_reason`` is available (e.g. ``length`` = output cap hit).

        Args:
            context: Formatted document context
            question: Current user question (last turn)
            history_messages: Prior conversation messages (HumanMessage / AIMessage)
            answer_depth_block: Injected ``ANSWER_DEPTH_INSTRUCTIONS`` block
        """
        chain = self.rag_prompt | self.llm
        _answer_stream_finish_reason.set(None)
        last_finish: Optional[str] = None
        try:
            async for chunk in chain.astream(
                {
                    "context": context,
                    "question": question,
                    "answer_depth_block": answer_depth_block,
                    "topic_composer_block": topic_composer_block,
                    "history": history_messages,
                    "user_preferences_block": user_preferences_block,
                }
            ):
                reason = _finish_reason_from_message_chunk(chunk)
                if reason:
                    last_finish = reason
                delta = _message_chunk_text_delta(chunk)
                if delta:
                    yield delta
        finally:
            _answer_stream_finish_reason.set(last_finish)
            if last_finish == "length":
                logger.warning(
                    "OpenAI answer stream ended with finish_reason=length (output budget); "
                    "consider OPENAI_MAX_COMPLETION_TOKENS or a narrower question."
                )

    async def astream_respond_direct(
        self,
        history_text: str,
        question: str,
        *,
        direct_mode: str = DirectMode.SMALLTALK.value,
        user_preferences_block: str = "",
    ) -> AsyncIterator[str]:
        """
        Stream response tokens for direct responses (no RAG).
        
        Args:
            history_text: Formatted conversation history
            question: User's question
            direct_mode: ``smalltalk`` or ``handbook`` (inlined handbook CONTEXT).
            
        Yields:
            Response tokens as they're generated
        """
        direct_mode_norm = str(direct_mode or DirectMode.SMALLTALK.value).strip().lower()
        use_handbook = direct_mode_norm == DirectMode.HANDBOOK.value and handbook_direct_enabled()
        handbook_blob = ""
        if use_handbook:
            try:
                handbook_blob = load_handbook_text()
            except FileNotFoundError:
                logger.warning("Handbook corpus missing at astream_respond_direct; using smalltalk.")
                use_handbook = False

        if use_handbook and handbook_blob:
            chain = self.handbook_prompt | self.llm
            stream_payload: dict[str, str] = {
                "history": history_text,
                "handbook_context": handbook_blob,
                "question": question,
                "user_preferences_block": user_preferences_block,
            }
        else:
            chain = self.direct_prompt | self.llm
            stream_payload = {
                "history": history_text,
                "question": question,
                "user_preferences_block": user_preferences_block,
            }

        _answer_stream_finish_reason.set(None)
        last_finish: Optional[str] = None
        try:
            async for chunk in chain.astream(stream_payload):
                reason = _finish_reason_from_message_chunk(chunk)
                if reason:
                    last_finish = reason
                delta = _message_chunk_text_delta(chunk)
                if delta:
                    yield delta
        finally:
            _answer_stream_finish_reason.set(last_finish)
            if last_finish == "length":
                logger.warning(
                    "OpenAI direct stream ended with finish_reason=length (output budget)."
                )
