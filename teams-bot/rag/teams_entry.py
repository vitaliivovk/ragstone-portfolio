"""Teams turn entry: inner RAG pipeline + :class:`StreamingResult` (no outer Deep Agent)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable, Optional

from bot.turn_latency import current_turn_latency

if TYPE_CHECKING:
    from .graph import RAGGraph, StreamingResult

logger = logging.getLogger(__name__)


async def astream_teams_entry(
    rag_graph: "RAGGraph",
    *,
    user_message: str,
    user_id: str,
    conversation_id: str,
    include_history: bool,
    on_optimize: Optional[Callable[..., Any]],
    on_retrieve: Optional[Callable[..., Any]],
    on_retrieval_phase: Optional[Callable[..., Any]],
    on_history_loading: Optional[Callable[[], Any]] = None,
    on_optimize_start: Optional[Callable[[], Any]] = None,
    on_answer_start: Optional[Callable[[], Any]] = None,
    persist_turn: bool = True,
) -> AsyncIterator["StreamingResult"]:
    """
    Teams path: run optimize → retrieve → answer, then yield a single authoritative
    :class:`StreamingResult` (citations + audit fields).

    ``conversation_id`` is stored on context-cache rows for future per-conversation scoping.

    When ``persist_turn`` is True (default, e.g. local harness), the turn is saved here.
    Azure Functions should pass ``persist_turn=False`` and schedule ``save_turn`` after the
    final Teams message is sent.
    """
    from .graph import StreamingResult

    stream_latency = current_turn_latency()
    if stream_latency:
        stream_latency.emit(
            "teams_entry_begin",
        )

    work = await rag_graph.build_teams_pipeline(
        user_message,
        user_id,
        include_history,
        on_optimize,
        on_retrieve,
        on_retrieval_phase,
        on_optimize_start=on_optimize_start,
        on_history_cache_miss=on_history_loading,
        conversation_id=conversation_id,
    )

    result = await rag_graph.complete_response_from_work(
        work,
        on_answer_start=on_answer_start,
    )

    if stream_latency:
        stream_latency.emit(
            "teams_entry_complete",
            needs_rag=result.needs_rag,
        )

    if persist_turn and result.full_response:
        await rag_graph.save_turn(user_id, user_message, result.full_response)
        await rag_graph.persist_rag_context_cache_from_work(
            work,
            conversation_id=conversation_id,
        )
        logger.info("Saved conversation turn for user %s", user_id)

    yield result


async def astream_teams_entry_tokens(
    rag_graph: "RAGGraph",
    *,
    user_message: str,
    user_id: str,
    conversation_id: str,
    include_history: bool,
    on_optimize: Optional[Callable[..., Any]],
    on_retrieve: Optional[Callable[..., Any]],
    on_retrieval_phase: Optional[Callable[..., Any]],
    on_history_loading: Optional[Callable[[], Any]] = None,
    on_optimize_start: Optional[Callable[[], Any]] = None,
    on_answer_start: Optional[Callable[[], Any]] = None,
    persist_turn: bool = True,
    external_history: Optional[list] = None,
) -> AsyncIterator[dict[str, Any]]:
    """
    Teams path with **token deltas** for TTFT, then a final ``{"type": "result", "value": StreamingResult}``.

    Yields ``{"type": "token", "delta": str}`` for visible answer text (a fully-formed legacy
    ``CITATIONS_USED:`` tail may be suppressed in deltas). Caller must still send citations via ``send_final``.

    When ``external_history`` is provided (web adapter), Table Storage history load is skipped.
    """
    from langchain_core.messages import BaseMessage

    from .citations import (
        precompute_streaming_citation_map,
        streaming_safe_answer_visible_text,
    )
    from .graph import StreamingResult, resolve_response_path, streaming_audit_fields_from_work
    from .answer_composer import build_topic_composer_block
    from .nodes import (
        ANSWER_DEPTH_INSTRUCTIONS,
        AnswerDepth,
        consume_answer_stream_finish_reason,
        format_history_for_prompt,
        postprocess_rag_answer_text_with_precomputed_map,
    )
    from .prompts import ANSWER_TRUNCATED_BY_LENGTH_SUFFIX

    stream_latency = current_turn_latency()
    if stream_latency:
        stream_latency.emit("teams_entry_begin")

    history_arg: Optional[list[BaseMessage]] = None
    if external_history is not None:
        history_arg = list(external_history)

    work = await rag_graph.build_teams_pipeline(
        user_message,
        user_id,
        include_history if history_arg is None else False,
        on_optimize,
        on_retrieve,
        on_retrieval_phase,
        on_optimize_start=on_optimize_start,
        on_history_cache_miss=on_history_loading,
        conversation_id=conversation_id,
        external_history=history_arg,
    )

    used_rag_context = (
        work.needs_rag
        and bool(str(work.context or "").strip())
        and bool(work.sources)
    )
    if work.needs_rag and not used_rag_context:
        logger.info(
            "Teams token stream: retrieval produced no context; using respond_direct "
            "instead of RAG on empty CONTEXT."
        )

    if on_answer_start is not None:
        await on_answer_start()

    if bool(work.optimize_result.get("clarification_needed")):
        merged_clarify = {**work.initial_state, **work.optimize_result}
        clarify_out = await rag_graph.nodes.respond_clarify(merged_clarify)
        audit_extra = streaming_audit_fields_from_work(
            work,
            response_path="clarify",
            context_sources=[],
        )
        yield {
            "type": "result",
            "value": StreamingResult(
                sources=[],
                needs_rag=False,
                full_response=clarify_out["response"],
                optimized_query=work.optimized_query,
                retrieval_scope=work.retrieval_scope_raw,
                corpus_path_prefixes=work.corpus_path_prefixes_resolved,
                search_focus=work.search_focus,
                optimizer_reasoning=work.optimizer_reasoning,
                pinecone_index=rag_graph._pinecone_index_name,
                pinecone_namespace=rag_graph._pinecone_namespace,
                pinecone_metadata_filter=work.pinecone_metadata_filter,
                retrieval_k=0,
                reuse_previous_context="none",
                answer_depth=str(work.optimize_result.get("answer_depth") or "").strip(),
                **audit_extra,
            ),
        }
        if persist_turn and clarify_out["response"]:
            await rag_graph.save_turn(user_id, user_message, clarify_out["response"])
        return

    prefs_block = str(work.initial_state.get("user_preferences_block") or "")

    raw_accum = ""
    emitted_visible_len = 0
    first_model_token = True

    if used_rag_context:
        depth_raw = (
            (work.optimize_result.get("answer_depth") or AnswerDepth.STANDARD.value)
            .strip()
            .lower()
        )
        depth_key = (
            depth_raw
            if depth_raw in ANSWER_DEPTH_INSTRUCTIONS
            else AnswerDepth.STANDARD.value
        )
        depth_block = ANSWER_DEPTH_INSTRUCTIONS[depth_key]
        topic_composer_block = build_topic_composer_block(
            str(work.optimize_result.get("answer_topic") or "none"),
            bool(work.optimize_result.get("numeric_answer_first")),
        )
        messages = work.initial_state["messages"]
        prior = messages[:-1]
        history_slice = prior[-12:] if prior else []

        # ``display_rows`` lists retrieved documents for **Źródła** (deduplicated).
        _, display_rows, _max_display = precompute_streaming_citation_map(
            work.sources
        )
        yield {
            "type": "sources",
            "sources": work.sources,
            "display_rows": display_rows,
        }

        async for chunk in rag_graph.nodes.astream_respond_with_rag(
            work.context,
            work.user_message,
            history_slice,
            depth_block,
            user_preferences_block=prefs_block,
            topic_composer_block=topic_composer_block,
        ):
            raw_accum += chunk
            visible = streaming_safe_answer_visible_text(raw_accum)
            if len(visible) > emitted_visible_len:
                delta = visible[emitted_visible_len:]
                emitted_visible_len = len(visible)
                if first_model_token and delta and stream_latency:
                    first_model_token = False
                    stream_latency.emit("orchestration_first_model_token")
                yield {"type": "token", "delta": delta}

        display, picked_sources, _citations_md, attach_sources_block = (
            postprocess_rag_answer_text_with_precomputed_map(raw_accum, display_rows)
        )
        truncated_by_cap = consume_answer_stream_finish_reason() == "length"
        if truncated_by_cap:
            display = f"{display.rstrip()}{ANSWER_TRUNCATED_BY_LENGTH_SUFFIX}"
        reuse_pc = str(work.optimize_result.get("reuse_previous_context") or "none")
        depth = str(work.optimize_result.get("answer_depth") or "").strip()
        audit_extra = streaming_audit_fields_from_work(
            work,
            response_path="rag",
            context_sources=work.sources,
        )
        result = StreamingResult(
            sources=picked_sources,
            needs_rag=True,
            full_response=display,
            attach_sources_block=attach_sources_block,
            optimized_query=work.optimized_query,
            retrieval_scope=work.retrieval_scope_raw,
            corpus_path_prefixes=work.corpus_path_prefixes_resolved,
            search_focus=work.search_focus,
            optimizer_reasoning=work.optimizer_reasoning,
            pinecone_index=rag_graph._pinecone_index_name,
            pinecone_namespace=rag_graph._pinecone_namespace,
            pinecone_metadata_filter=work.pinecone_metadata_filter,
            retrieval_k=work.num_docs,
            retrieval_fallback_unfiltered=work.retrieval_fallback_unfiltered,
            reuse_previous_context=reuse_pc,
            answer_depth=depth,
            output_truncated_by_max_tokens=truncated_by_cap,
            **audit_extra,
        )
    else:
        history_text = format_history_for_prompt(work.initial_state["messages"][:-1])
        direct_mode = str(work.optimize_result.get("direct_mode") or "smalltalk")
        async for chunk in rag_graph.nodes.astream_respond_direct(
            history_text,
            work.user_message,
            direct_mode=direct_mode,
            user_preferences_block=prefs_block,
        ):
            raw_accum += chunk
            if first_model_token and chunk and stream_latency:
                first_model_token = False
                stream_latency.emit("orchestration_first_model_token")
            yield {"type": "token", "delta": chunk}

        display_direct = raw_accum.strip()
        truncated_by_cap = consume_answer_stream_finish_reason() == "length"
        if truncated_by_cap:
            display_direct = f"{display_direct.rstrip()}{ANSWER_TRUNCATED_BY_LENGTH_SUFFIX}"
        reuse_pc = str(work.optimize_result.get("reuse_previous_context") or "none")
        depth = str(work.optimize_result.get("answer_depth") or "").strip()
        response_path = resolve_response_path(
            clarification_needed=False,
            used_rag_context=False,
            direct_mode=direct_mode,
        )
        audit_extra = streaming_audit_fields_from_work(
            work,
            response_path=response_path,
            context_sources=[],
        )
        result = StreamingResult(
            sources=[],
            needs_rag=False,
            full_response=display_direct,
            optimized_query=work.optimized_query,
            retrieval_scope=work.retrieval_scope_raw,
            corpus_path_prefixes=work.corpus_path_prefixes_resolved,
            search_focus=work.search_focus,
            optimizer_reasoning=work.optimizer_reasoning,
            pinecone_index=rag_graph._pinecone_index_name,
            pinecone_namespace=rag_graph._pinecone_namespace,
            pinecone_metadata_filter=work.pinecone_metadata_filter,
            retrieval_k=0,
            retrieval_fallback_unfiltered=False,
            reuse_previous_context=reuse_pc,
            answer_depth=depth,
            output_truncated_by_max_tokens=truncated_by_cap,
            **audit_extra,
        )

    if stream_latency:
        stream_latency.emit("teams_entry_complete", needs_rag=result.needs_rag)

    if persist_turn and result.full_response:
        await rag_graph.save_turn(user_id, user_message, result.full_response)
        await rag_graph.persist_rag_context_cache_from_work(
            work,
            conversation_id=conversation_id,
        )
        logger.info("Saved conversation turn for user %s", user_id)

    yield {"type": "result", "value": result, "work": work}


async def invoke_teams_turn(
    rag_graph: "RAGGraph",
    *,
    user_message: str,
    user_id: str,
    conversation_id: str = "",
    include_history: bool = True,
) -> dict[str, Any]:
    """Non-streaming invoke for tests and tooling (saves when storage is configured)."""
    result = await rag_graph.run_teams_turn_nonstream(
        user_message,
        user_id,
        include_history,
        on_optimize=None,
        on_retrieve=None,
        on_retrieval_phase=None,
        persist_turn=True,
        conversation_id=conversation_id,
    )
    return {
        "response": result.full_response,
        "sources": result.sources,
        "needs_rag": result.needs_rag,
        "optimized_query": result.optimized_query,
        "retrieval_scope": result.retrieval_scope,
    }
