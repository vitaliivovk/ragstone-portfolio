"""LangGraph workflow for the RAG chatbot with conditional routing."""
import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Annotated, Any, List, Optional, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from bot.turn_latency import current_turn_latency
from config import OpenAIConfig, PineconeConfig, StorageConfig
from .context_cache import ContextCache
from .memory import TableStorageMemory
from .nodes import RAGNodes, format_history_for_prompt
from .user_preferences import UserPreferencesStore, format_user_preferences_prompt_block
from .retrieval_filter import (
    RetrievalScope,
    build_pinecone_filter_for_retrieval,
    coalesce_path_prefixes_from_state,
    coalesce_retrieval_scopes_from_state,
)


logger = logging.getLogger(__name__)


class ChatState(TypedDict):
    """
    State for the RAG chatbot workflow.
    
    Attributes:
        messages: Conversation history (managed by add_messages reducer)
        user_id: Teams user ID for memory isolation
        needs_rag: Whether document retrieval is needed
        optimized_query: Rewritten query for vector search
        num_documents: Target chunk count for retrieval (2-8)
        retrieval_tier: summary_then_chunks or chunks_only
        search_focus: Type of search (specific/broad/none)
        retrieval_scopes: Corpus topic slugs for Pinecone (OR); use ["all"] for no topic filter
        context: Formatted document context
        sources: Source metadata for citations
        response: Generated response text
        citations: Formatted citations markdown
    """
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    needs_rag: bool
    optimized_query: str
    num_documents: int
    retrieval_tier: str
    search_focus: str
    retrieval_scopes: List[str]
    context: str
    sources: list[dict]
    retrieved_docs: list
    response: str
    citations: str
    corpus_path_prefixes: List[str]
    corpus_file_name: str
    corpus_source_relative_path: str
    answer_depth: str
    reuse_previous_context: str
    direct_mode: str
    clarification_needed: bool
    clarification_questions: List[str]
    cached_rag_entry: Optional[dict[str, Any]]
    user_preferences_block: str


@dataclass
class StreamingResult:
    """Result from streaming token generation."""
    sources: list[dict]
    needs_rag: bool
    full_response: str
    attach_sources_block: bool = False
    optimized_query: str = ""
    retrieval_scope: str = "all"  # comma-separated corpusTopic slugs for audit / Teams metadata
    corpus_path_prefixes: List[str] = field(default_factory=list)
    search_focus: str = "none"
    optimizer_reasoning: str = ""
    pinecone_index: str = ""
    pinecone_namespace: str = ""
    pinecone_metadata_filter: Optional[dict] = None
    retrieval_k: int = 0
    retrieval_fallback_unfiltered: bool = False
    reuse_previous_context: str = "none"
    answer_depth: str = ""
    output_truncated_by_max_tokens: bool = False
    optimizer_saw_cached_retrieval: bool = False
    cached_retrieval_age_min: Optional[float] = None
    cached_retrieval_files: List[str] = field(default_factory=list)
    conversation_id: str = ""
    response_path: str = ""
    clarification_needed: bool = False
    clarification_questions: List[str] = field(default_factory=list)
    answer_topic: str = "none"
    numeric_answer_first: bool = False
    context_chunk_ids: List[str] = field(default_factory=list)


def resolve_response_path(
    *,
    clarification_needed: bool,
    used_rag_context: bool,
    direct_mode: str,
) -> str:
    """Audit label for which answer branch produced the outbound text."""
    if clarification_needed:
        return "clarify"
    if used_rag_context:
        return "rag"
    if str(direct_mode or "").strip().lower() == "handbook":
        return "handbook"
    return "smalltalk"


def streaming_audit_fields_from_work(
    work: "TeamsRagPipelineContext",
    *,
    response_path: str,
    context_sources: list[dict],
) -> dict[str, Any]:
    """Shared audit payload fields for StreamingResult and log_rag_turn_audit."""
    from .request_audit import context_chunk_ids_from_sources

    opt = work.optimize_result
    return {
        "conversation_id": work.conversation_id,
        "response_path": response_path,
        "clarification_needed": bool(opt.get("clarification_needed")),
        "clarification_questions": list(opt.get("clarification_questions") or []),
        "answer_topic": str(opt.get("answer_topic") or "none"),
        "numeric_answer_first": bool(opt.get("numeric_answer_first")),
        "context_chunk_ids": context_chunk_ids_from_sources(context_sources),
    }


def _cached_retrieval_audit_fields(
    cached_entry: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """Distill ContextCache row into the three audit-only fields shipped per turn.

    ``seen`` is True whenever the optimizer was given a non-empty cached entry —
    even if it ultimately picked ``reuse_previous_context=none``. Useful in KQL to
    measure how often the optimizer is presented with cache vs. how often it
    actually decides to reuse / augment.
    """
    if not cached_entry:
        return {"seen": False, "age_min": None, "files": []}
    sources = cached_entry.get("sources") or []
    files: List[str] = []
    seen_paths: set[str] = set()
    if isinstance(sources, list):
        for src in sources:
            if not isinstance(src, dict):
                continue
            label = (
                str(src.get("sourceRelativePath") or "").strip()
                or str(src.get("fileName") or "").strip()
            )
            if not label or label in seen_paths:
                continue
            seen_paths.add(label)
            files.append(label)
            if len(files) >= 5:
                break
    age_min: Optional[float] = None
    ts_raw = str(cached_entry.get("timestamp") or "").strip()
    if ts_raw:
        try:
            ts_dt = datetime.fromisoformat(ts_raw)
            if ts_dt.tzinfo is None:
                ts_dt = ts_dt.replace(tzinfo=timezone.utc)
            age_min = max(0.0, (datetime.now(timezone.utc) - ts_dt).total_seconds() / 60)
        except ValueError:
            age_min = None
    return {"seen": True, "age_min": age_min, "files": files}


@dataclass
class TeamsRagPipelineContext:
    """Shared optimize + retrieve phase for Teams and local harness."""

    initial_state: ChatState
    history: list[BaseMessage]
    user_message: str
    optimize_result: dict[str, Any]
    needs_rag: bool
    num_docs: int
    optimized_query: str
    retrieval_scope_raw: str
    corpus_path_prefixes_resolved: List[str]
    search_focus: str
    optimizer_reasoning: str
    pinecone_metadata_filter: Optional[dict]
    sources: list[dict]
    context: str
    retrieval_fallback_unfiltered: bool
    retrieved_docs: list[Any] = field(default_factory=list)
    conversation_id: str = ""


def route_after_optimize(state: ChatState) -> str:
    """
    Conditional routing based on RAG strategy decision.
    
    Routes to:
    - "respond_clarify" when optimizer requests clarifying questions (no retrieval)
    - "retrieve" if RAG is needed
    - "respond_direct" if no RAG needed
    """
    if state.get("clarification_needed", False):
        return "respond_clarify"
    if state.get("needs_rag", False):
        return "retrieve"
    return "respond_direct"


def route_after_retrieve(state: ChatState) -> str:
    """
    After Pinecone: use RAG answer only when we actually have chunk context.

    When retrieval returns no rows, skip ``respond_with_rag`` (empty CONTEXT
    otherwise invites hallucinated citations) and fall back to ``respond_direct``.
    """
    context_text = str(state.get("context") or "").strip()
    sources = state.get("sources") or []
    if context_text and sources:
        return "respond_with_rag"
    return "respond_direct"


class RAGGraph:
    """
    LangGraph-based RAG workflow with conditional routing and memory.
    
    Flow:
    1. Load history from Table Storage
    2. Optimize: LLM decides RAG strategy
    3. Route: If needs_rag -> retrieve, else -> direct response
    4. Generate: Create response with or without context
    5. Save: Store conversation turn in memory
    """
    
    def __init__(
        self,
        openai_config: OpenAIConfig,
        pinecone_config: PineconeConfig,
        storage_connection_string: Optional[str] = None,
        *,
        storage: Optional[StorageConfig] = None,
    ):
        """
        Initialize the RAG graph.

        Args:
            openai_config: OpenAI configuration
            pinecone_config: Pinecone configuration
            storage: Optional full storage config (preferred; includes history limits + cache)
            storage_connection_string: Legacy Azure Storage connection string for memory only
        """
        resolved_storage: StorageConfig
        if storage is not None:
            resolved_storage = storage
        elif storage_connection_string:
            resolved_storage = StorageConfig(connection_string=storage_connection_string)
        else:
            resolved_storage = StorageConfig()

        self._history_limit_default = resolved_storage.history_limit_default
        self._storage_config = resolved_storage

        # Answer LLM (respond_with_rag / respond_direct), optimizer, embeddings.
        # ``reasoning_effort="minimal"`` disables internal reasoning steps for the
        # gpt-5-* family so structured optimizer routing and grounded answers stream
        # at non-reasoning latency. We do not set ``temperature`` for these reasoning
        # models because OpenAI rejects non-default values on the reasoning API.
        self.llm = ChatOpenAI(
            model=openai_config.model,
            openai_api_key=openai_config.api_key,
            reasoning_effort="minimal",
            model_kwargs={
                "max_completion_tokens": openai_config.max_completion_tokens,
            },
        )
        self.optimizer_llm = ChatOpenAI(
            model=openai_config.optimizer_model,
            openai_api_key=openai_config.api_key,
            reasoning_effort="minimal",
        )

        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings(
            model=openai_config.embedding_model,
            openai_api_key=openai_config.api_key,
        )
        
        # Initialize vector store
        self.vectorstore = PineconeVectorStore(
            index_name=pinecone_config.index_name,
            embedding=self.embeddings,
            namespace=pinecone_config.namespace,
            pinecone_api_key=pinecone_config.api_key,
        )
        self._pinecone_index_name = pinecone_config.index_name
        self._pinecone_namespace = pinecone_config.namespace
        logger.info(
            "Pinecone vector store: index=%s namespace=%s",
            pinecone_config.index_name,
            pinecone_config.namespace,
        )
        logger.info(
            "OpenAI chat models: answers=%s optimizer=%s",
            openai_config.model,
            openai_config.optimizer_model,
        )

        # Initialize memory (optional)
        self.memory: Optional[TableStorageMemory] = None
        self.context_cache: Optional[ContextCache] = None
        self.user_preferences: Optional[UserPreferencesStore] = None
        if resolved_storage.enabled and resolved_storage.connection_string:
            connection_string = resolved_storage.connection_string
            self.memory = TableStorageMemory(
                connection_string,
                history_cache_ttl_seconds=resolved_storage.history_cache_ttl_seconds,
                history_cache_max_users=resolved_storage.history_cache_max_users,
            )
            self.context_cache = ContextCache(connection_string)
            self.user_preferences = UserPreferencesStore(connection_string)

        # Initialize nodes
        self.nodes = RAGNodes(
            llm=self.llm,
            optimizer_llm=self.optimizer_llm,
            embeddings=self.embeddings,
            vectorstore=self.vectorstore,
            pinecone_config=pinecone_config,
        )
        
        # Build the graph
        self.graph = self._build_graph()

    async def _load_user_preferences_block(self, user_id: str) -> str:
        """Formatted prompt fragment for per-user /style preferences, or empty string."""
        if self.user_preferences is None:
            return ""
        try:
            raw = await self.user_preferences.get_text(user_id)
        except Exception as exc:
            logger.warning("User preferences load failed: %s", exc)
            return ""
        return format_user_preferences_prompt_block(raw)

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        # Create the graph
        workflow = StateGraph(ChatState)
        
        # Add nodes
        workflow.add_node("optimize", self.nodes.optimize)
        workflow.add_node("retrieve", self.nodes.retrieve)
        workflow.add_node("respond_with_rag", self.nodes.respond_with_rag)
        workflow.add_node("respond_direct", self.nodes.respond_direct)
        workflow.add_node("respond_clarify", self.nodes.respond_clarify)
        
        # Add edges
        workflow.add_edge(START, "optimize")
        
        # Conditional routing after optimization
        workflow.add_conditional_edges(
            "optimize",
            route_after_optimize,
            {
                "retrieve": "retrieve",
                "respond_direct": "respond_direct",
                "respond_clarify": "respond_clarify",
            }
        )
        
        workflow.add_conditional_edges(
            "retrieve",
            route_after_retrieve,
            {
                "respond_with_rag": "respond_with_rag",
                "respond_direct": "respond_direct",
            },
        )

        # Both response paths lead to END
        workflow.add_edge("respond_with_rag", END)
        workflow.add_edge("respond_direct", END)
        workflow.add_edge("respond_clarify", END)
        
        # Compile the graph
        return workflow.compile()
    
    async def load_history(
        self,
        user_id: str,
        limit: Optional[int] = None,
        *,
        on_cache_miss: Optional[Callable[[], Awaitable[None]]] = None,
    ) -> list[BaseMessage]:
        """
        Load conversation history from memory.

        Args:
            user_id: Teams user ID
            limit: Maximum messages to load; ``None`` uses ``StorageConfig.history_limit_default``;
                ``-1`` loads all messages from storage for this user
            on_cache_miss: Optional callback when a Table Storage read is required (cache miss)

        Returns:
            List of messages in chronological order
        """
        if self.memory is None:
            raise RuntimeError(
                "Conversation memory is required but storage is not configured "
                "(set AZURE_STORAGE_CONNECTION_STRING or AzureWebJobsStorage)"
            )
        resolved_limit = self._history_limit_default if limit is None else limit
        try:
            history = await self.memory.get_history(
                user_id,
                limit=resolved_limit,
                on_cache_miss=on_cache_miss,
            )
            logger.info(
                "Loaded %s messages from history for user %s",
                len(history),
                user_id,
            )
            return history
        except Exception as exc:
            logger.error("Error loading history: %s", exc)
            raise
    
    async def save_turn(
        self,
        user_id: str,
        user_message: str,
        assistant_message: str,
    ) -> None:
        """
        Save a conversation turn to memory.
        
        Args:
            user_id: Teams user ID
            user_message: The user's message
            assistant_message: The assistant's response
        """
        if not self.memory:
            return
        
        try:
            await self.memory.save_conversation_turn(
                user_id=user_id,
                user_message=user_message,
                assistant_message=assistant_message,
            )
        except Exception as exc:
            logger.error(f"Error saving turn: {exc}")

    async def persist_rag_context_cache_from_work(
        self,
        work: TeamsRagPipelineContext,
        *,
        conversation_id: str = "",
    ) -> None:
        """Store last retrieval for reuse/augment (skipped when no chunk rows were fetched)."""
        if self.context_cache is None or not work.needs_rag or not work.retrieved_docs:
            return
        user_id = work.initial_state["user_id"]
        chunk_ids: list[str] = []
        from .pinecone_ids import chunk_vector_id

        for doc in work.retrieved_docs:
            meta = doc.metadata
            doc_id = meta.get("docId")
            chunk_idx = meta.get("chunkIndex")
            if doc_id is None or chunk_idx is None:
                continue
            chunk_ids.append(chunk_vector_id(str(doc_id), int(chunk_idx)))
        try:
            await self.context_cache.save(
                user_id,
                optimized_query=work.optimized_query,
                context_text=work.context,
                sources=work.sources,
                chunk_ids=chunk_ids,
                conversation_id=conversation_id,
            )
        except Exception as exc:
            logger.warning("Context cache save failed: %s", exc)

    async def purge_stale_storage(self) -> dict[str, int]:
        """
        Purge old conversation rows and context cache rows (Timer Trigger).

        Returns counts ``{"conversations": n, "context_cache": m}``.
        """
        out = {"conversations": 0, "context_cache": 0}
        cfg = self._storage_config
        if self.memory is not None and cfg.history_ttl_hours > 0:
            out["conversations"] = await self.memory.purge_messages_older_than_hours(
                cfg.history_ttl_hours
            )
        if self.context_cache is not None and cfg.context_cache_ttl_hours > 0:
            out["context_cache"] = await self.context_cache.purge_older_than_hours(
                cfg.context_cache_ttl_hours
            )
        return out

    async def run(
        self,
        user_message: str,
        user_id: str,
        include_history: bool = True,
        *,
        persist_turn: bool = True,
    ) -> dict[str, Any]:
        """
        Run the RAG workflow.
        
        Args:
            user_message: The user's current message
            user_id: Teams user ID for memory isolation
            include_history: Whether to load conversation history
            persist_turn: When False, skip saving to conversation memory (e.g. Azure Functions schedules save after final message).
            
        Returns:
            Final state with response, citations, and metadata
        """
        # Load history if enabled
        history: list[BaseMessage] = []
        if include_history:
            history = await self.load_history(user_id)

        prefs_block = await self._load_user_preferences_block(user_id)

        # Build initial state
        initial_state: ChatState = {
            "messages": history + [HumanMessage(content=user_message)],
            "user_id": user_id,
            "needs_rag": False,
            "optimized_query": "",
            "num_documents": 0,
            "retrieval_tier": "chunks_only",
            "search_focus": "none",
            "retrieval_scopes": [RetrievalScope.ALL.value],
            "context": "",
            "sources": [],
            "retrieved_docs": [],
            "response": "",
            "citations": "",
            "corpus_path_prefixes": [],
            "corpus_file_name": "",
            "corpus_source_relative_path": "",
            "answer_depth": "",
            "reuse_previous_context": "none",
            "direct_mode": "smalltalk",
            "cached_rag_entry": None,
            "user_preferences_block": prefs_block,
        }

        # Run the graph
        logger.info("Running graph for user %s", user_id)
        final_state = await self.graph.ainvoke(initial_state)
        
        # Save the turn to memory
        response = final_state.get("response", "")
        if persist_turn and response:
            await self.save_turn(user_id, user_message, response)
        
        return final_state
    
    async def astream(
        self,
        user_message: str,
        user_id: str,
        include_history: bool = True,
    ):
        """
        Stream the RAG workflow for real-time updates.
        
        Yields state updates as the graph progresses.
        
        Args:
            user_message: The user's current message
            user_id: Teams user ID
            include_history: Whether to load conversation history
            
        Yields:
            State updates from each node
        """
        # Load history if enabled
        history: list[BaseMessage] = []
        if include_history:
            history = await self.load_history(user_id)

        prefs_block = await self._load_user_preferences_block(user_id)

        # Build initial state
        initial_state: ChatState = {
            "messages": history + [HumanMessage(content=user_message)],
            "user_id": user_id,
            "needs_rag": False,
            "optimized_query": "",
            "num_documents": 0,
            "retrieval_tier": "chunks_only",
            "search_focus": "none",
            "retrieval_scopes": [RetrievalScope.ALL.value],
            "context": "",
            "sources": [],
            "retrieved_docs": [],
            "response": "",
            "citations": "",
            "corpus_path_prefixes": [],
            "corpus_file_name": "",
            "corpus_source_relative_path": "",
            "answer_depth": "",
            "reuse_previous_context": "none",
            "direct_mode": "smalltalk",
            "cached_rag_entry": None,
            "user_preferences_block": prefs_block,
        }

        # Stream the graph
        logger.info("Streaming graph for user %s", user_id)
        
        response_text = ""
        async for event in self.graph.astream(initial_state):
            yield event
            
            # Extract response from response nodes
            # Event structure is {node_name: node_output}
            for node_name, node_output in event.items():
                if node_name in ("respond_with_rag", "respond_direct"):
                    response_text = node_output.get("response", "")
        
        # Save the turn to memory after streaming completes
        if response_text:
            await self.save_turn(user_id, user_message, response_text)
            logger.info("Saved conversation turn for user %s", user_id)
    
    async def build_teams_pipeline(
        self,
        user_message: str,
        user_id: str,
        include_history: bool,
        on_optimize: Optional[
            Callable[..., Awaitable[None]]
        ] = None,
        on_retrieve: Optional[
            Callable[..., Awaitable[None]]
        ] = None,
        on_retrieval_phase: Optional[
            Callable[[str, dict[str, Any]], Awaitable[None]]
        ] = None,
        *,
        on_optimize_start: Optional[Callable[[], Awaitable[None]]] = None,
        on_history_cache_miss: Optional[Callable[[], Awaitable[None]]] = None,
        conversation_id: str = "",
        external_history: Optional[list[BaseMessage]] = None,
    ) -> TeamsRagPipelineContext:
        """
        Shared optimize + retrieve phase for Teams status callbacks.

        When ``external_history`` is set (web / OpenAI-compat path), Table Storage
        memory is skipped and that list is used as prior turns.
        """
        history: list[BaseMessage] = []
        if external_history is not None:
            history = list(external_history)
        elif include_history:
            history = await self.load_history(
                user_id,
                on_cache_miss=on_history_cache_miss,
            )

        prefs_block = await self._load_user_preferences_block(user_id)

        initial_state: ChatState = {
            "messages": history + [HumanMessage(content=user_message)],
            "user_id": user_id,
            "needs_rag": False,
            "optimized_query": "",
            "num_documents": 0,
            "retrieval_tier": "chunks_only",
            "search_focus": "none",
            "retrieval_scopes": [RetrievalScope.ALL.value],
            "context": "",
            "sources": [],
            "retrieved_docs": [],
            "response": "",
            "citations": "",
            "corpus_path_prefixes": [],
            "corpus_file_name": "",
            "corpus_source_relative_path": "",
            "answer_depth": "",
            "reuse_previous_context": "none",
            "direct_mode": "smalltalk",
            "clarification_needed": False,
            "clarification_questions": [],
            "cached_rag_entry": None,
            "user_preferences_block": prefs_block,
        }

        logger.info("Teams RAG pipeline (optimize/retrieve) for user %s", user_id)

        # Load the previous turn's retrieval (if any) BEFORE the optimizer call so the
        # optimizer can decide reuse / augment / none informed by what was actually
        # cached. Run in parallel with the "Planuję wyszukiwanie…" informative POST so
        # the Table Storage round-trip is hidden in user-perceived latency. Filtered
        # by ``conversation_id`` to avoid leaking context across chat threads.
        cached_entry_task: Optional[asyncio.Task[Optional[dict[str, Any]]]] = None
        if self.context_cache is not None:
            async def _fetch_cached_entry() -> Optional[dict[str, Any]]:
                try:
                    return await self.context_cache.get_latest(
                        user_id, conversation_id=conversation_id,
                    )
                except Exception as exc:
                    logger.warning("Context cache get_latest failed: %s", exc)
                    return None
            cached_entry_task = asyncio.create_task(_fetch_cached_entry())

        if on_optimize_start is not None:
            await on_optimize_start()

        cached_rag_entry: Optional[dict[str, Any]] = None
        if cached_entry_task is not None:
            cached_rag_entry = await cached_entry_task
        initial_state["cached_rag_entry"] = cached_rag_entry

        t_opt = time.monotonic()
        optimize_result = await self.nodes.optimize(initial_state)
        optimize_ms = (time.monotonic() - t_opt) * 1000
        logger.info(
            "teams_pipeline_optimize_ms=%.0f needs_rag=%s",
            optimize_ms,
            optimize_result.get("needs_rag"),
        )
        latency = current_turn_latency()
        if latency:
            latency.emit(
                "inner_rag_optimize_complete",
                segment_ms=round(optimize_ms, 2),
                needs_rag=bool(optimize_result.get("needs_rag", False)),
            )
        needs_rag = optimize_result.get("needs_rag", False)
        clarification_needed = bool(optimize_result.get("clarification_needed", False))
        num_docs = optimize_result.get("num_documents", 4)
        optimized_query = optimize_result.get("optimized_query", "")
        search_focus = optimize_result.get("search_focus", "none")
        optimizer_reasoning = optimize_result.get("optimizer_reasoning", "")

        merged_for_filter = {**initial_state, **optimize_result}
        scopes_resolved = coalesce_retrieval_scopes_from_state(merged_for_filter)
        prefix_list = coalesce_path_prefixes_from_state(merged_for_filter)
        corpus_file_raw = (optimize_result.get("corpus_file_name") or "").strip()
        corpus_rel_raw = (optimize_result.get("corpus_source_relative_path") or "").strip()
        pinecone_metadata_filter = build_pinecone_filter_for_retrieval(
            scopes_resolved,
            corpus_path_prefixes=prefix_list or None,
            corpus_file_name=corpus_file_raw,
            corpus_source_relative_path=corpus_rel_raw,
        )
        retrieval_scope_raw = ",".join(scope.value for scope in scopes_resolved)

        retrieval_tier_raw = optimize_result.get("retrieval_tier", "")
        if on_optimize:
            await on_optimize(
                needs_rag,
                num_docs,
                retrieval_scopes=[scope.value for scope in scopes_resolved],
                retrieval_tier=retrieval_tier_raw,
                corpus_path_prefixes=prefix_list,
                corpus_file_name=corpus_file_raw,
                corpus_source_relative_path=corpus_rel_raw,
            )

        sources: list[dict] = []
        context = ""
        retrieval_fallback_unfiltered = False
        retrieved_docs: list[Any] = []

        if clarification_needed:
            if latency:
                latency.emit("inner_rag_retrieve_skipped", reason="clarification_needed")
        elif needs_rag:
            retrieve_state = {
                **initial_state,
                **optimize_result,
                "cached_rag_entry": cached_rag_entry,
            }
            self.nodes.set_retrieval_phase_callback(on_retrieval_phase)
            try:
                t_ret = time.monotonic()
                retrieve_result = await self.nodes.retrieve(retrieve_state)
                retrieve_ms = (time.monotonic() - t_ret) * 1000
                logger.info(
                    "teams_pipeline_retrieve_ms=%.0f sources=%s",
                    retrieve_ms,
                    len(retrieve_result.get("sources", [])),
                )
                if latency:
                    latency.emit(
                        "inner_rag_retrieve_complete",
                        segment_ms=round(retrieve_ms, 2),
                        source_count=len(retrieve_result.get("sources", [])),
                    )
            finally:
                self.nodes.set_retrieval_phase_callback(None)
            sources = retrieve_result.get("sources", [])
            context = retrieve_result.get("context", "")
            retrieval_fallback_unfiltered = bool(
                retrieve_result.get("retrieval_fallback_unfiltered", False)
            )
            retrieved_docs = retrieve_result.get("retrieved_docs", []) or []

            if on_retrieve:
                await on_retrieve(
                    len(sources),
                    fallback_unfiltered=retrieval_fallback_unfiltered,
                )

        else:
            if latency:
                latency.emit("inner_rag_retrieve_skipped", reason="needs_rag_false")

        return TeamsRagPipelineContext(
            initial_state=initial_state,
            history=history,
            user_message=user_message,
            optimize_result=optimize_result,
            needs_rag=needs_rag,
            num_docs=num_docs,
            optimized_query=optimized_query,
            retrieval_scope_raw=retrieval_scope_raw,
            corpus_path_prefixes_resolved=prefix_list,
            search_focus=search_focus,
            optimizer_reasoning=optimizer_reasoning,
            pinecone_metadata_filter=pinecone_metadata_filter,
            sources=sources,
            context=context,
            retrieval_fallback_unfiltered=retrieval_fallback_unfiltered,
            retrieved_docs=retrieved_docs,
            conversation_id=conversation_id,
        )

    async def complete_response_from_work(
        self,
        work: TeamsRagPipelineContext,
        *,
        on_answer_start: Optional[Callable[[], Awaitable[None]]] = None,
    ) -> StreamingResult:
        """Generate the assistant reply from optimize/retrieve context (no save)."""
        if on_answer_start is not None:
            await on_answer_start()

        if bool(work.optimize_result.get("clarification_needed")):
            merged_clarify = {**work.initial_state, **work.optimize_result}
            t_ans = time.monotonic()
            out = await self.nodes.respond_clarify(merged_clarify)
            respond_ms = (time.monotonic() - t_ans) * 1000
            logger.info("teams_pipeline_respond_clarify_ms=%.0f", respond_ms)
            latency_clarify = current_turn_latency()
            if latency_clarify:
                latency_clarify.emit(
                    "inner_rag_respond_complete",
                    branch="respond_clarify",
                    segment_ms=round(respond_ms, 2),
                )
            cache_audit = _cached_retrieval_audit_fields(
                work.initial_state.get("cached_rag_entry")
            )
            audit_extra = streaming_audit_fields_from_work(
                work,
                response_path="clarify",
                context_sources=[],
            )
            return StreamingResult(
                sources=[],
                needs_rag=False,
                full_response=out["response"],
                attach_sources_block=False,
                optimized_query=work.optimized_query,
                retrieval_scope=work.retrieval_scope_raw,
                corpus_path_prefixes=work.corpus_path_prefixes_resolved,
                search_focus=work.search_focus,
                optimizer_reasoning=work.optimizer_reasoning,
                pinecone_index=self._pinecone_index_name,
                pinecone_namespace=self._pinecone_namespace,
                pinecone_metadata_filter=work.pinecone_metadata_filter,
                retrieval_k=0,
                retrieval_fallback_unfiltered=False,
                reuse_previous_context="none",
                answer_depth=str(work.optimize_result.get("answer_depth") or "").strip(),
                optimizer_saw_cached_retrieval=cache_audit["seen"],
                cached_retrieval_age_min=cache_audit["age_min"],
                cached_retrieval_files=cache_audit["files"],
                **audit_extra,
            )

        used_rag_context = (
            work.needs_rag
            and bool(str(work.context or "").strip())
            and bool(work.sources)
        )
        if work.needs_rag and not used_rag_context:
            logger.info(
                "Skipping respond_with_rag: optimizer requested RAG but retrieval "
                "produced no usable context; using respond_direct (smalltalk)."
            )

        if used_rag_context:
            merged: dict[str, Any] = {
                **work.initial_state,
                **work.optimize_result,
                "context": work.context,
                "sources": work.sources,
            }
            t_ans = time.monotonic()
            out = await self.nodes.respond_with_rag(merged)
            respond_ms = (time.monotonic() - t_ans) * 1000
            logger.info(
                "teams_pipeline_respond_rag_ms=%.0f",
                respond_ms,
            )
            display_answer = out["response"]
            picked_sources = out["sources"]
            respond_branch = "respond_with_rag"
        else:
            merged_direct = {**work.initial_state, **work.optimize_result}
            if work.needs_rag and not used_rag_context:
                merged_direct["needs_rag"] = False
                merged_direct["direct_mode"] = "smalltalk"
            t_ans = time.monotonic()
            out = await self.nodes.respond_direct(merged_direct)
            respond_ms = (time.monotonic() - t_ans) * 1000
            logger.info(
                "teams_pipeline_respond_direct_ms=%.0f",
                respond_ms,
            )
            display_answer = out["response"]
            picked_sources = []
            respond_branch = "respond_direct"

        latency_answer = current_turn_latency()
        if latency_answer:
            latency_answer.emit(
                "inner_rag_respond_complete",
                branch=respond_branch,
                segment_ms=round(respond_ms, 2),
            )

        reuse_pc = str(work.optimize_result.get("reuse_previous_context") or "none")
        depth = str(work.optimize_result.get("answer_depth") or "").strip()
        cache_audit = _cached_retrieval_audit_fields(
            work.initial_state.get("cached_rag_entry")
        )
        direct_mode = str(work.optimize_result.get("direct_mode") or "smalltalk")
        response_path = resolve_response_path(
            clarification_needed=False,
            used_rag_context=used_rag_context,
            direct_mode=direct_mode,
        )
        context_sources = work.sources if used_rag_context else []
        audit_extra = streaming_audit_fields_from_work(
            work,
            response_path=response_path,
            context_sources=context_sources,
        )
        return StreamingResult(
            sources=picked_sources,
            needs_rag=used_rag_context,
            full_response=display_answer,
            attach_sources_block=bool(out.get("attach_sources_block")),
            optimized_query=work.optimized_query,
            retrieval_scope=work.retrieval_scope_raw,
            corpus_path_prefixes=work.corpus_path_prefixes_resolved,
            search_focus=work.search_focus,
            optimizer_reasoning=work.optimizer_reasoning,
            pinecone_index=self._pinecone_index_name,
            pinecone_namespace=self._pinecone_namespace,
            pinecone_metadata_filter=work.pinecone_metadata_filter,
            retrieval_k=work.num_docs if used_rag_context else 0,
            retrieval_fallback_unfiltered=work.retrieval_fallback_unfiltered,
            reuse_previous_context=reuse_pc,
            answer_depth=depth,
            optimizer_saw_cached_retrieval=cache_audit["seen"],
            cached_retrieval_age_min=cache_audit["age_min"],
            cached_retrieval_files=cache_audit["files"],
            **audit_extra,
        )

    async def run_teams_turn_nonstream(
        self,
        user_message: str,
        user_id: str,
        include_history: bool = True,
        on_optimize: Optional[
            Callable[..., Awaitable[None]]
        ] = None,
        on_retrieve: Optional[
            Callable[..., Awaitable[None]]
        ] = None,
        on_retrieval_phase: Optional[
            Callable[[str, dict[str, Any]], Awaitable[None]]
        ] = None,
        *,
        persist_turn: bool = True,
        on_optimize_start: Optional[Callable[[], Awaitable[None]]] = None,
        on_answer_start: Optional[Callable[[], Awaitable[None]]] = None,
        on_history_cache_miss: Optional[Callable[[], Awaitable[None]]] = None,
        conversation_id: str = "",
    ) -> StreamingResult:
        """
        Full inner RAG turn without token streaming (local harness and tooling).
        """
        work = await self.build_teams_pipeline(
            user_message,
            user_id,
            include_history,
            on_optimize,
            on_retrieve,
            on_retrieval_phase,
            on_optimize_start=on_optimize_start,
            on_history_cache_miss=on_history_cache_miss,
            conversation_id=conversation_id,
        )
        result = await self.complete_response_from_work(
            work,
            on_answer_start=on_answer_start,
        )

        if persist_turn and result.full_response:
            await self.save_turn(user_id, user_message, result.full_response)
            logger.info("Saved conversation turn for user %s", user_id)
            await self.persist_rag_context_cache_from_work(
                work,
                conversation_id=conversation_id,
            )

        return result
