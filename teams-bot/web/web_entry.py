"""Web-channel turn runner: OpenAI-compat events over the Teams RAG pipeline."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional

from bot.status_copy import (
    after_optimize_message,
    after_retrieve_message,
    analyzing_question,
    answer_composing_message,
    optimizer_planning_message,
    retrieval_phase_message,
)
from rag.citations import (
    format_citations_from_display_rows,
    should_attach_source_block,
    streaming_safe_answer_visible_text,
)
from rag.graph import StreamingResult
from rag.request_audit import log_rag_turn_audit
from rag.teams_entry import astream_teams_entry_tokens
from web.openai_compat import (
    ChatCompletionRequest,
    append_sources_markdown,
    chat_completion_chunk,
    chat_completion_response,
    new_completion_id,
    sse_data_line,
)

if TYPE_CHECKING:
    from rag.graph import RAGGraph

logger = logging.getLogger(__name__)


async def astream_web_openai_events(
    rag_graph: "RAGGraph",
    request: ChatCompletionRequest,
    *,
    persist_context_cache: bool = True,
) -> AsyncIterator[dict[str, Any]]:
    """
    Yield OpenAI chat.completion.chunk dicts (stream path) ending with a finish chunk.

    Polish pipeline status is emitted as ``reasoning_content`` deltas before/around
    answer tokens. Table Storage conversation history is not loaded or saved; LibreChat
    owns history. Context cache rows still use ``X-User-ID`` + ``X-Conversation-ID``.
    """
    completion_id = new_completion_id()
    created = int(time.time())
    model = request.model

    yield chat_completion_chunk(
        completion_id=completion_id,
        model=model,
        created=created,
        role="assistant",
        reasoning_content=analyzing_question(),
    )

    _pending_status: list[str] = []
    display_rows: list[dict] = []
    stream_turn_result: Optional[StreamingResult] = None
    pipeline_work: Any = None
    answer_body = ""

    async def on_optimize_start() -> None:
        _pending_status.append(optimizer_planning_message())

    async def on_answer_start() -> None:
        _pending_status.append(answer_composing_message())

    async def on_optimize(
        needs_rag: bool,
        num_docs: int,
        *,
        retrieval_scopes: list[str] | None = None,
        retrieval_tier: str = "",
        corpus_path_prefixes: list[str] | None = None,
        corpus_file_name: str = "",
        corpus_source_relative_path: str = "",
    ) -> None:
        del retrieval_tier
        text = after_optimize_message(
            needs_rag=needs_rag,
            num_docs=num_docs,
            retrieval_scopes=retrieval_scopes if retrieval_scopes else ["all"],
            corpus_path_prefixes=corpus_path_prefixes or [],
            corpus_file_name=corpus_file_name,
            corpus_source_relative_path=corpus_source_relative_path,
        )
        _pending_status.append(text)

    async def on_retrieve(
        num_sources: int,
        *,
        fallback_unfiltered: bool = False,
    ) -> None:
        _pending_status.append(
            after_retrieve_message(
                num_sources,
                fallback_unfiltered=fallback_unfiltered,
            )
        )

    async def on_retrieval_phase(phase: str, info: dict) -> None:
        text = retrieval_phase_message(phase, info)
        if text:
            _pending_status.append(text)

    async for event in astream_teams_entry_tokens(
        rag_graph,
        user_message=request.user_message,
        user_id=request.user_id,
        conversation_id=request.conversation_id,
        include_history=False,
        on_optimize=on_optimize,
        on_retrieve=on_retrieve,
        on_retrieval_phase=on_retrieval_phase,
        on_optimize_start=on_optimize_start,
        on_answer_start=on_answer_start,
        persist_turn=False,
        external_history=request.history,
    ):
        while _pending_status:
            status = _pending_status.pop(0)
            yield chat_completion_chunk(
                completion_id=completion_id,
                model=model,
                created=created,
                reasoning_content=status,
            )

        event_type = event.get("type")
        if event_type == "sources":
            display_rows = event.get("display_rows") or []
            continue

        if event_type == "token":
            delta = str(event.get("delta") or "")
            if not delta:
                continue
            answer_body += delta
            yield chat_completion_chunk(
                completion_id=completion_id,
                model=model,
                created=created,
                content=delta,
            )
            continue

        if event_type == "result":
            item = event["value"]
            if isinstance(item, StreamingResult):
                stream_turn_result = item
                pipeline_work = event.get("work")
            continue

    while _pending_status:
        status = _pending_status.pop(0)
        yield chat_completion_chunk(
            completion_id=completion_id,
            model=model,
            created=created,
            reasoning_content=status,
        )

    full_response = ""
    attach = False
    if stream_turn_result is not None:
        full_response = stream_turn_result.full_response or ""
        attach = bool(stream_turn_result.attach_sources_block)
        log_rag_turn_audit(
            logger,
            teams_user_id=request.user_id,
            teams_user_name="",
            user_message=request.user_message,
            assistant_response=full_response,
            needs_rag=stream_turn_result.needs_rag,
            optimized_query=stream_turn_result.optimized_query,
            retrieval_scope=stream_turn_result.retrieval_scope,
            search_focus=stream_turn_result.search_focus,
            optimizer_reasoning=stream_turn_result.optimizer_reasoning,
            pinecone_index=stream_turn_result.pinecone_index,
            pinecone_namespace=stream_turn_result.pinecone_namespace,
            pinecone_metadata_filter=stream_turn_result.pinecone_metadata_filter,
            retrieval_k=stream_turn_result.retrieval_k,
            retrieval_fallback_unfiltered=stream_turn_result.retrieval_fallback_unfiltered,
            retrieved_sources=stream_turn_result.sources,
            corpus_path_prefixes=stream_turn_result.corpus_path_prefixes,
            answer_depth=stream_turn_result.answer_depth,
            output_truncated_by_max_tokens=stream_turn_result.output_truncated_by_max_tokens,
            reuse_previous_context=stream_turn_result.reuse_previous_context,
            optimizer_saw_cached_retrieval=stream_turn_result.optimizer_saw_cached_retrieval,
            cached_retrieval_age_min=stream_turn_result.cached_retrieval_age_min,
            cached_retrieval_files=stream_turn_result.cached_retrieval_files,
            conversation_id=stream_turn_result.conversation_id or request.conversation_id,
            response_path=stream_turn_result.response_path,
            clarification_needed=stream_turn_result.clarification_needed,
            clarification_questions=stream_turn_result.clarification_questions,
            answer_topic=stream_turn_result.answer_topic,
            numeric_answer_first=stream_turn_result.numeric_answer_first,
            context_chunk_ids=stream_turn_result.context_chunk_ids,
            channel="web",
        )

    # If streaming truncated mid-answer relative to authoritative full_response,
    # append the missing tail (same post-processed body Teams uses for send_final).
    authoritative = (full_response or "").strip()
    streamed_visible = streaming_safe_answer_visible_text(answer_body).strip()
    if authoritative and authoritative != streamed_visible:
        if authoritative.startswith(streamed_visible):
            tail = authoritative[len(streamed_visible) :]
            if tail:
                yield chat_completion_chunk(
                    completion_id=completion_id,
                    model=model,
                    created=created,
                    content=tail,
                )
        else:
            # Non-prefix case (clarify / direct): replace by sending remaining if empty stream
            if not streamed_visible:
                yield chat_completion_chunk(
                    completion_id=completion_id,
                    model=model,
                    created=created,
                    content=authoritative,
                )

    citations_suffix = ""
    if display_rows and (
        attach or should_attach_source_block(authoritative or answer_body)
    ):
        citations = format_citations_from_display_rows(display_rows)
        if citations:
            citations_suffix = f"\n\n**Źródła:**\n{citations}"
            yield chat_completion_chunk(
                completion_id=completion_id,
                model=model,
                created=created,
                content=citations_suffix,
            )

    if persist_context_cache and pipeline_work is not None:
        try:
            await rag_graph.persist_rag_context_cache_from_work(
                pipeline_work,
                conversation_id=request.conversation_id,
            )
        except Exception:
            logger.exception("Web path: context cache persist failed")

    yield chat_completion_chunk(
        completion_id=completion_id,
        model=model,
        created=created,
        finish_reason="stop",
    )


async def complete_web_openai_response(
    rag_graph: "RAGGraph",
    request: ChatCompletionRequest,
    *,
    persist_context_cache: bool = True,
) -> dict[str, Any]:
    """Non-streaming ``chat.completion`` object (full answer + Źródła)."""
    content_parts: list[str] = []
    async for chunk in astream_web_openai_events(
        rag_graph,
        request,
        persist_context_cache=persist_context_cache,
    ):
        choices = chunk.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        piece = delta.get("content")
        if piece:
            content_parts.append(str(piece))
    completion_id = new_completion_id()
    created = int(time.time())
    return chat_completion_response(
        completion_id=completion_id,
        model=request.model,
        created=created,
        content="".join(content_parts),
    )


def format_sse_stream(
    chunks: AsyncIterator[dict[str, Any]],
) -> AsyncIterator[str]:
    """Wrap chunk dicts as SSE ``data:`` lines plus a terminal ``[DONE]``."""

    async def _gen() -> AsyncIterator[str]:
        async for chunk in chunks:
            yield sse_data_line(chunk)
        yield "data: [DONE]\n\n"

    return _gen()


__all__ = [
    "astream_web_openai_events",
    "complete_web_openai_response",
    "format_sse_stream",
    "append_sources_markdown",
]
