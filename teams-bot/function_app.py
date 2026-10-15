"""Azure Functions entry point for the Teams Bot."""
import asyncio
import json
import logging
import os
import threading
import time
from typing import Any, Optional

import azure.functions as func

from bot.activity_handler import parse_teams_activity
from bot.style_commands import parse_style_command
from bot.status_copy import (
    after_optimize_message,
    after_retrieve_message,
    analyzing_question,
    answer_composing_message,
    history_loading_question,
    optimizer_planning_message,
    retrieval_phase_message,
)
from bot.streaming import (
    StreamingProtocolError,
    StreamingStoppedError,
    TeamsStreamer,
)
from bot.turn_latency import current_turn_latency, turn_latency_scope
from rag.citations import (
    format_citations_from_display_rows,
    should_attach_source_block,
    streaming_safe_answer_visible_text,
)
from rag.graph import StreamingResult
from rag.request_audit import log_rag_turn_audit
from rag.teams_entry import astream_teams_entry_tokens


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_background_save_tasks: set[asyncio.Task[Any]] = set()


def _normalize_teams_slash_command(message_text: str) -> str:
    """Strip Teams bot @mentions from slash commands (e.g. ``/cmd@BotName``)."""
    stripped = message_text.strip().lower()
    if "@" in stripped:
        stripped = stripped.split("@", 1)[0].strip()
    return stripped


def schedule_conversation_save(
    graph: Any,
    user_id: str,
    user_message: str,
    assistant_message: str,
) -> None:
    """Persist turn after Teams final message; keeps host alive until the task finishes."""

    async def _save() -> None:
        try:
            await graph.save_turn(user_id, user_message, assistant_message)
        except Exception:
            logger.exception("Background save_turn failed for user %s", user_id)

    task = asyncio.create_task(_save())
    _background_save_tasks.add(task)
    task.add_done_callback(_background_save_tasks.discard)


def schedule_turn_and_context_cache_save(
    graph: Any,
    user_id: str,
    user_message: str,
    assistant_message: str,
    pipeline_work: Any,
    conversation_id: str,
) -> None:
    """Persist conversation turn and RAG context cache row (background)."""

    async def _save() -> None:
        try:
            await graph.save_turn(user_id, user_message, assistant_message)
            if pipeline_work is not None:
                await graph.persist_rag_context_cache_from_work(
                    pipeline_work,
                    conversation_id=conversation_id,
                )
        except Exception:
            logger.exception(
                "Background save_turn / context_cache failed for user %s",
                user_id,
            )

    task = asyncio.create_task(_save())
    _background_save_tasks.add(task)
    task.add_done_callback(_background_save_tasks.discard)


class _InformativeThrottler:
    """Send at most one informative per second per logical key (Teams rate limit)."""

    def __init__(self, streamer: TeamsStreamer, min_interval: float = 1.0):
        self._streamer = streamer
        self._min_interval = min_interval
        self._last_key: str | None = None
        self._last_time = 0.0

    async def send(self, key: str, text: str) -> None:
        now = time.time()
        if self._last_key == key and now - self._last_time < self._min_interval:
            return
        await self._streamer.send_informative(
            text,
            latency_case=f"status_progress:{key}",
        )
        self._last_key = key
        self._last_time = now


# Create the Function App
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Global config and graph (lazy initialization)
_config = None
_rag_graph = None
_rag_graph_lock = threading.Lock()


def get_config():
    """Lazy load configuration."""
    global _config
    if _config is None:
        from config import load_config
        _config = load_config()
    return _config


def get_rag_graph():
    """Lazy load RAG graph (thread-safe; double-checked under lock so the background
    pre-warm thread and the first user request don't both pay the ~900 ms ChatOpenAI /
    Pinecone client init)."""
    global _rag_graph
    if _rag_graph is not None:
        return _rag_graph
    with _rag_graph_lock:
        if _rag_graph is not None:
            return _rag_graph
        from rag import RAGGraph
        config = get_config()
        _rag_graph = RAGGraph(
            openai_config=config.openai,
            pinecone_config=config.pinecone,
            storage=config.storage,
        )
        logger.info(
            f"RAG Graph initialized. Memory enabled: {config.storage.enabled}"
        )
        return _rag_graph


def _prewarm_rag_graph_in_background() -> None:
    """Best-effort background pre-warm at module import.

    Eliminates the ~900 ms RAG-graph init cost from the first user-facing turn after
    a Function instance spin-up. Runs on a daemon thread so import never blocks; if
    init fails (e.g. transient network), the next request just falls through to the
    normal lazy init in :func:`get_rag_graph`.
    """
    def _warm() -> None:
        try:
            get_rag_graph()
            logger.info("RAG graph pre-warm complete (background)")
        except Exception:
            logger.exception(
                "RAG graph pre-warm failed; first request will lazy-init"
            )

    threading.Thread(target=_warm, daemon=True, name="rag-prewarm").start()


_prewarm_rag_graph_in_background()


async def process_message(
    activity_body: dict,
    *,
    azure_invocation_id: str = "",
) -> None:
    """
    Process a message with inner RAG (optimize → retrieve → answer) and stream to Teams.

    Flow:
    1. Informative update: "Analizuję pytanie…"
    2. Status lines during history load, optimizer, retrieval phases, and before answer LLM
    3. Stream authoritative answer from :class:`StreamingResult`; send final message with citations
    4. Schedule conversation save in the background (after final message)
    """
    activity = parse_teams_activity(activity_body)
    if not activity:
        logger.warning("Could not parse activity, skipping")
        return

    with turn_latency_scope(azure_invocation_id, logger) as turn_trace:
        turn_trace.emit(
            "turn_begin",
            teams_user_id=activity.user_id,
            teams_user_prefix=activity.user_id[:8],
            is_group_chat=activity.is_group_chat,
        )

        slash_cmd = _normalize_teams_slash_command(activity.message_text)
        if slash_cmd in ("/clean_chat_history", "/clear_history", "/wyczysc_historie"):
            turn_trace.emit("history_cleared", command=slash_cmd)
            graph = get_rag_graph()
            if graph.memory is None:
                await send_simple_reply(
                    activity_body,
                    "Nie można wyczyścić historii — pamięć rozmów nie jest skonfigurowana. Skontaktuj się z działem IT.",
                )
                return
            try:
                deleted_msgs = await graph.memory.clear_history(activity.user_id)
            except Exception:
                logger.exception("Failed to clear chat history for user %s", activity.user_id)
                await send_simple_reply(
                    activity_body,
                    "Nie udało się wyczyścić historii. Spróbuj ponownie za chwilę lub skontaktuj się z działem IT.",
                )
                return
            deleted_ctx = 0
            if graph.context_cache is not None:
                try:
                    deleted_ctx = await graph.context_cache.clear_user_context(activity.user_id)
                except Exception:
                    logger.exception(
                        "Context cache clear failed for user %s (history was cleared anyway)",
                        activity.user_id,
                    )
            logger.info(
                "Cleared chat history for user %s: conversation_rows=%s context_cache_rows=%s",
                activity.user_id,
                deleted_msgs,
                deleted_ctx,
            )
            await send_simple_reply(
                activity_body,
                "Historia rozmowy została wyczyszczona. Zaczynamy od nowa.",
            )
            return

        style_parsed = parse_style_command(slash_cmd, activity.message_text)
        if style_parsed is not None:
            style_kind, style_payload = style_parsed
            turn_trace.emit("style_command", kind=style_kind)
            graph = get_rag_graph()
            if graph.user_preferences is None:
                await send_simple_reply(
                    activity_body,
                    "Nie można zapisać preferencji — magazyn danych nie jest skonfigurowany. Skontaktuj się z działem IT.",
                )
                return
            try:
                if style_kind == "get":
                    current = await graph.user_preferences.get_text(activity.user_id)
                    if current:
                        await send_simple_reply(
                            activity_body,
                            f"**Twoje preferencje odpowiedzi (/style):**\n{current}",
                        )
                    else:
                        await send_simple_reply(
                            activity_body,
                            "Nie masz ustawionych preferencji. Napisz np. `/style krótko, w punktach` lub `/style odpowiadaj po angielsku`.",
                        )
                elif style_kind == "clear":
                    await graph.user_preferences.clear(activity.user_id)
                    await send_simple_reply(
                        activity_body,
                        "Preferencje stylu zostały usunięte. Odpowiedzi wracają do domyślnego trybu.",
                    )
                else:
                    stored = await graph.user_preferences.set_text(
                        activity.user_id, style_payload
                    )
                    await send_simple_reply(
                        activity_body,
                        f"Zapisano preferencje. Będę je uwzględniał w kolejnych odpowiedziach:\n{stored}",
                    )
            except Exception:
                logger.exception("Style command failed for user %s", activity.user_id)
                await send_simple_reply(
                    activity_body,
                    "Nie udało się zapisać preferencji. Spróbuj ponownie za chwilę.",
                )
            return

        config = get_config()

        try:
            async with TeamsStreamer(
                activity=activity,
                app_id=config.bot.app_id,
                app_password=config.bot.app_password,
            ) as streamer:
                logger.info("Sending informative: analyzing query...")
                latency = current_turn_latency()
                if latency:
                    latency.emit("orchestration_streamer_ready")
                await streamer.send_informative(
                    analyzing_question(),
                    latency_case="status_initial_analyzing",
                )
                # Lazy-init the RAG graph AFTER the first informative POST so the user
                # sees the streaming bubble within ~600 ms instead of paying ~900 ms of
                # ChatOpenAI / Pinecone client setup before any UI feedback. Once the
                # graph is cached, subsequent turns skip this entirely.
                graph = get_rag_graph()
                if latency:
                    latency.emit("orchestration_rag_graph_ready")
                informative = _InformativeThrottler(
                    streamer,
                    min_interval=TeamsStreamer.RATE_LIMIT_SECONDS,
                )

                async def on_history_loading() -> None:
                    await informative.send(
                        "status:history",
                        history_loading_question(),
                    )

                async def on_optimize_start() -> None:
                    await informative.send(
                        "status:optimizer",
                        optimizer_planning_message(),
                    )

                async def on_answer_start() -> None:
                    await informative.send(
                        "status:answer",
                        answer_composing_message(),
                    )

                async def on_optimize(
                    needs_rag: bool,
                    num_docs: int,
                    *,
                    retrieval_scopes: list[str] | None = None,
                    retrieval_tier: str = "",
                    corpus_path_prefixes: list[str] | None = None,
                    corpus_file_name: str = "",
                    corpus_source_relative_path: str = "",
                ):
                    del retrieval_tier
                    scopes = retrieval_scopes if retrieval_scopes else ["all"]
                    prefixes = corpus_path_prefixes or []
                    text = after_optimize_message(
                        needs_rag=needs_rag,
                        num_docs=num_docs,
                        retrieval_scopes=scopes,
                        corpus_path_prefixes=prefixes,
                        corpus_file_name=corpus_file_name,
                        corpus_source_relative_path=corpus_source_relative_path,
                    )
                    scope_key = ",".join(scopes)
                    await informative.send(
                        f"optimize:{needs_rag}:{scope_key}",
                        text,
                    )

                async def on_retrieve(
                    num_sources: int,
                    *,
                    fallback_unfiltered: bool = False,
                ):
                    logger.info(
                        "Retrieved %s sources (fallback_unfiltered=%s)",
                        num_sources,
                        fallback_unfiltered,
                    )
                    text = after_retrieve_message(
                        num_sources,
                        fallback_unfiltered=fallback_unfiltered,
                    )
                    await informative.send(
                        f"retrieve:{num_sources}:{fallback_unfiltered}",
                        text,
                    )

                async def on_retrieval_phase(phase: str, info: dict):
                    text = retrieval_phase_message(phase, info)
                    if text:
                        await informative.send(f"phase:{phase}", text)

                logger.info("Running turn for user %s", activity.user_id)

                sources: list[dict] = []
                full_response = ""
                stream_turn_result: Optional[StreamingResult] = None
                pipeline_work: Any = None
                answer_body = ""
                # ``display_rows`` arrive on the ``sources`` event before any token
                # (deduplicated document list for **Źródła**). Live chunks use
                # ``streaming_safe_answer_visible_text`` (no inline citation remap).
                stream_display_rows: list[dict] = []
                last_streamed_text = ""
                first_chunk_sent = False
                last_chunk_send_time = 0.0
                stream_protocol_broken = False

                async for event in astream_teams_entry_tokens(
                    graph,
                    user_message=activity.message_text,
                    user_id=activity.user_id,
                    conversation_id=activity.conversation_id,
                    include_history=True,
                    on_optimize=on_optimize,
                    on_retrieve=on_retrieve,
                    on_retrieval_phase=on_retrieval_phase,
                    on_history_loading=on_history_loading,
                    on_optimize_start=on_optimize_start,
                    on_answer_start=on_answer_start,
                    persist_turn=False,
                ):
                    event_type = event.get("type")
                    if event_type == "sources":
                        stream_display_rows = event.get("display_rows") or []
                        continue

                    if event_type == "token":
                        delta = str(event.get("delta") or "")
                        if not delta:
                            continue
                        answer_body += delta
                        if stream_protocol_broken:
                            continue
                        # Visible prefix matches post-processed body (no ``[Źródło N]``
                        # in the model contract). Hides partial legacy ``CITATIONS_USED:`` tails.
                        candidate = streaming_safe_answer_visible_text(answer_body)
                        if not candidate or len(candidate) <= len(last_streamed_text):
                            continue
                        if not candidate.startswith(last_streamed_text):
                            # Defensive: never emit something that is not a strict
                            # extension of the previous chunk. If the safe-prefix
                            # ever drifts (should not happen with the helpers above),
                            # we wait for the next token and retry.
                            continue
                        now = time.time()
                        if (
                            first_chunk_sent
                            and (now - last_chunk_send_time)
                            < TeamsStreamer.RATE_LIMIT_SECONDS
                        ):
                            continue
                        if (
                            not first_chunk_sent
                            and len(candidate)
                            < TeamsStreamer.STREAMING_MIN_CHARS_BEFORE_FIRST_SEND
                        ):
                            continue
                        if not first_chunk_sent:
                            if latency := current_turn_latency():
                                latency.emit("orchestration_first_model_token_received")
                                latency.emit("orchestration_authoritative_stream_start")
                        try:
                            await streamer.send_chunk(
                                candidate,
                                latency_case="answer_chunk_progress",
                            )
                        except StreamingProtocolError:
                            # Should be unreachable now that the streamed text is
                            # already remapped with the same map ``send_final`` will
                            # use, but keep the safety net so a regression never
                            # leaves the user with a frozen bubble — fall back to a
                            # single ``send_message`` after the stream completes.
                            logger.warning(
                                "send_chunk rejected by Teams despite precomputed"
                                " remap; aborting live stream and shipping the"
                                " authoritative answer as one message."
                            )
                            stream_protocol_broken = True
                            continue
                        last_streamed_text = candidate
                        last_chunk_send_time = now
                        first_chunk_sent = True
                        continue

                    if event_type == "result":
                        item = event["value"]
                        if not isinstance(item, StreamingResult):
                            continue
                        stream_turn_result = item
                        pipeline_work = event.get("work")
                        sources = item.sources
                        full_response = item.full_response
                        log_rag_turn_audit(
                            logger,
                            teams_user_id=activity.user_id,
                            teams_user_name=activity.user_name,
                            user_message=activity.message_text,
                            assistant_response=item.full_response,
                            needs_rag=item.needs_rag,
                            optimized_query=item.optimized_query,
                            retrieval_scope=item.retrieval_scope,
                            search_focus=item.search_focus,
                            optimizer_reasoning=item.optimizer_reasoning,
                            pinecone_index=item.pinecone_index,
                            pinecone_namespace=item.pinecone_namespace,
                            pinecone_metadata_filter=item.pinecone_metadata_filter,
                            retrieval_k=item.retrieval_k,
                            retrieval_fallback_unfiltered=item.retrieval_fallback_unfiltered,
                            retrieved_sources=item.sources,
                            corpus_path_prefixes=item.corpus_path_prefixes,
                            azure_invocation_id=azure_invocation_id,
                            answer_depth=item.answer_depth,
                            output_truncated_by_max_tokens=item.output_truncated_by_max_tokens,
                            reuse_previous_context=item.reuse_previous_context,
                            optimizer_saw_cached_retrieval=item.optimizer_saw_cached_retrieval,
                            cached_retrieval_age_min=item.cached_retrieval_age_min,
                            cached_retrieval_files=item.cached_retrieval_files,
                            conversation_id=item.conversation_id or activity.conversation_id,
                            response_path=item.response_path,
                            clarification_needed=item.clarification_needed,
                            clarification_questions=item.clarification_questions,
                            answer_topic=item.answer_topic,
                            numeric_answer_first=item.numeric_answer_first,
                            context_chunk_ids=item.context_chunk_ids,
                        )
                        continue

                if full_response.strip():
                    # ``full_response`` is post-processed inside the token generator
                    # (strip legacy tails and any stray ``[Źródło N]``). **Źródła** come
                    # from ``stream_display_rows`` (retrieval), not from model inline tags.
                    citations_block = ""
                    if stream_display_rows and (
                        (stream_turn_result is not None and stream_turn_result.attach_sources_block)
                        or should_attach_source_block(full_response)
                    ):
                        citations = format_citations_from_display_rows(
                            stream_display_rows
                        )
                        if citations:
                            citations_block = f"**Źródła:**\n{citations}"

                    final_body = full_response.strip()
                    final_text = final_body
                    if citations_block:
                        final_text = f"{final_body}\n\n\n{citations_block}"

                    if not stream_protocol_broken:
                        try:
                            await streamer.send_final(
                                final_text,
                                sources,
                                latency_case=(
                                    "final_with_source_block"
                                    if citations_block else "final_answer_body_only"
                                ),
                            )
                        except StreamingProtocolError:
                            logger.warning(
                                "send_final rejected with ContentStreamNotAllowed;"
                                " falling back to a non-streaming send_message."
                            )
                            stream_protocol_broken = True

                    if stream_protocol_broken:
                        # Defensive recovery: a rejected chunk/final left a partial
                        # streaming bubble (often still showing ``[Źródło N]``).
                        # Best-effort DELETE avoids duplicate partial + fallback
                        # message in Teams (see ``TeamsStreamer.delete_stream_activity``).
                        deleted_partial = await streamer.delete_stream_activity()
                        if deleted_partial:
                            logger.info(
                                "Removed partial streaming activity before fallback send_message"
                            )
                        else:
                            logger.warning(
                                "Could not delete partial stream activity; user may see two bubbles"
                            )
                        if latency := current_turn_latency():
                            latency.emit(
                                "answer_split_for_delivery",
                                answer_chars=len(full_response),
                                body_message_count=1,
                                citations_inlined=bool(citations_block),
                                reason="content_stream_not_allowed",
                            )
                        await streamer.send_message(
                            final_text,
                            latency_case="fallback_full_answer",
                        )

                    if latency := current_turn_latency():
                        latency.emit("orchestration_authoritative_stream_end")

                    logger.info("Response complete!")
                    schedule_turn_and_context_cache_save(
                        graph,
                        activity.user_id,
                        activity.message_text,
                        full_response,
                        pipeline_work,
                        activity.conversation_id,
                    )
                else:
                    await streamer.send_final(
                        "Przepraszam, nie udało się wygenerować odpowiedzi.",
                        [],
                        latency_case="final_no_model_output",
                    )

                if latency := current_turn_latency():
                    latency.emit("turn_complete", outcome="ok")

        except StreamingStoppedError:
            logger.info("User stopped the streaming response")
            if latency := current_turn_latency():
                latency.emit("turn_complete", outcome="user_stopped_stream")
        except Exception as exc:
            logger.exception(f"Error in process_message: {exc}")
            if latency := current_turn_latency():
                latency.emit(
                    "turn_complete",
                    outcome="error",
                    error_type=type(exc).__name__,
                )
            from rag.prompts import ERROR_MESSAGE

            try:
                await send_simple_reply(activity_body, ERROR_MESSAGE)
            except Exception as send_exc:
                logger.exception(f"Failed to send error message: {send_exc}")


@app.route(route="messages", methods=["POST"])
async def teams_webhook(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    """
    Handle incoming Teams Bot Framework activities.
    
    Process messages and send responses via Teams API.
    """
    try:
        # Parse the activity
        body = req.get_json()
        activity_type = body.get("type", "")
        
        logger.info(f"Received activity: {activity_type}")
        logger.debug(f"Full body: {json.dumps(body)[:500]}")
        
        # For message activities, process with RAG graph
        if activity_type == "message":
            inv = getattr(context, "invocation_id", "") or ""
            logger.info("teams_webhook invocation_id=%s", inv)
            await process_message(body, azure_invocation_id=inv)
        
        # Return 200 OK to Bot Framework
        return func.HttpResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
        )
        
    except ValueError as exc:
        logger.error(f"Invalid JSON in request: {exc}")
        return func.HttpResponse(
            body=json.dumps({"error": "Invalid JSON"}),
            status_code=400,
            headers={"Content-Type": "application/json"},
        )
    except Exception as exc:
        logger.exception(f"Error handling webhook: {exc}")
        return func.HttpResponse(
            body=json.dumps({"error": "Internal server error"}),
            status_code=500,
            headers={"Content-Type": "application/json"},
        )


async def send_simple_reply(activity: dict, text: str) -> None:
    """Send a simple text reply to test connectivity."""
    import aiohttp
    import urllib.parse
    
    config = get_config()
    
    tenant_id = os.environ["MICROSOFT_APP_TENANT_ID"]
    
    # Get token - use tenant-specific endpoint for SingleTenant
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    token_data = {
        "grant_type": "client_credentials",
        "client_id": config.bot.app_id,
        "client_secret": config.bot.app_password,
        "scope": "https://api.botframework.com/.default",
    }
    
    async with aiohttp.ClientSession() as session:
        # Get token
        async with session.post(token_url, data=token_data) as resp:
            if resp.status != 200:
                error = await resp.text()
                logger.error(f"Token error: {error}")
                return
            token_result = await resp.json()
            token = token_result["access_token"]
        
        # Send reply
        service_url = activity.get("serviceUrl", "").rstrip("/")
        conversation_id = urllib.parse.quote(
            activity.get("conversation", {}).get("id", "")
        )
        url = f"{service_url}/v3/conversations/{conversation_id}/activities"
        
        reply = {
            "type": "message",
            "text": text,
            "textFormat": "markdown",
            "from": activity.get("recipient"),
            "recipient": activity.get("from"),
            "conversation": activity.get("conversation"),
            "replyToId": activity.get("id"),
        }
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        async with session.post(url, json=reply, headers=headers) as resp:
            if resp.status not in (200, 201, 202):
                error = await resp.text()
                logger.error(f"Reply error: {resp.status} - {error}")
            else:
                logger.info("Reply sent successfully!")


@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint."""
    config = get_config()
    return func.HttpResponse(
        body=json.dumps({
            "status": "healthy",
            "service": "Northwind Assistant Bot",
            "features": {
                "langgraph": True,
                "memory": config.storage.enabled,
                "conditional_rag": True,
            },
        }),
        status_code=200,
        headers={"Content-Type": "application/json"},
    )


def _prewarm_worker() -> None:
    """Warm RAG graph construction and Bot Framework token (best-effort; never raises)."""
    raw = os.environ.get("RAGSTONE_DISABLE_PREWARM", "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return
    try:
        from bot.bot_framework_token import prefetch_bot_framework_token
        from config import load_config
        from rag.graph import RAGGraph

        cfg = load_config()
        RAGGraph(
            openai_config=cfg.openai,
            pinecone_config=cfg.pinecone,
            storage=cfg.storage,
        )
        logger.info("Prewarm: RAGGraph constructor completed")
        asyncio.run(
            prefetch_bot_framework_token(
                app_id=cfg.bot.app_id,
                app_password=cfg.bot.app_password,
            )
        )
    except Exception as exc:
        logger.warning("Prewarm failed: %s", exc)


@app.function_name("purge_stale_storage")
@app.timer_trigger(
    schedule="0 0 * * * *",
    arg_name="purge_timer",
    run_on_startup=False,
    use_monitor=False,
)
async def purge_stale_storage(purge_timer: func.TimerRequest) -> None:
    """Hourly (UTC) purge of expired conversation rows and RAG context cache (see StorageConfig TTL env)."""
    if purge_timer.past_due:
        logger.info("purge_stale_storage: timer past_due flag set")
    graph = get_rag_graph()
    try:
        counts = await graph.purge_stale_storage()
        logger.info("purge_stale_storage complete: %s", counts)
    except Exception:
        logger.exception("purge_stale_storage failed")


def _schedule_startup_prewarm() -> None:
    thread = threading.Thread(
        target=_prewarm_worker,
        name="ragstone-prewarm",
        daemon=True,
    )
    thread.start()


_schedule_startup_prewarm()
