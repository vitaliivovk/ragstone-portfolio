"""
FastAPI OpenAI-compatible facade for LibreChat (Phase 1).

Hosting choice: **FastAPI sidecar** (not Azure Functions HTTP). Functions can stream
but SSE + long-lived connections are awkward on the Python worker; this sidecar
shares the same ``rag/`` code and env as the Teams Function App and can later sit
on Azure Container Apps next to LibreChat.

Run (from ``teams-bot/``)::

    set RAG_WEB_API_KEY=dev-key
    set OPENAI_API_KEY=...
    set PINECONE_API_KEY=...
    python -m web.app

Default listen: ``http://127.0.0.1:8081`` — LibreChat ``baseURL``:
``http://host.docker.internal:8081/v1``.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from web.openai_compat import (
    AuthError,
    BadRequestError,
    DEFAULT_MODEL_ID,
    models_list_payload,
    parse_chat_completion_request,
    require_bearer_api_key,
)
from web.web_entry import (
    astream_web_openai_events,
    complete_web_openai_response,
    format_sse_stream,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RAGStone OpenAI-compatible adapter", version="0.1.0")

_rag_graph = None
_rag_graph_lock = threading.Lock()


def get_rag_graph():
    """Lazy RAGGraph (same stack as Functions; no Bot Framework credentials required)."""
    global _rag_graph
    if _rag_graph is not None:
        return _rag_graph
    with _rag_graph_lock:
        if _rag_graph is not None:
            return _rag_graph
        from config import load_rag_stack_settings
        from rag import RAGGraph

        openai_cfg, pinecone_cfg, storage_cfg = load_rag_stack_settings()
        _rag_graph = RAGGraph(
            openai_config=openai_cfg,
            pinecone_config=pinecone_cfg,
            storage=storage_cfg,
        )
        logger.info(
            "Web RAG graph ready (memory=%s namespace=%s)",
            storage_cfg.enabled,
            pinecone_cfg.namespace,
        )
        return _rag_graph


def _auth_or_401(authorization: Optional[str]) -> None:
    try:
        require_bearer_api_key(authorization)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "rag-web-adapter"}


@app.get("/v1/models")
async def list_models(
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _auth_or_401(authorization)
    return models_list_payload(model_id=os.environ.get("RAG_WEB_MODEL_ID", DEFAULT_MODEL_ID))


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-ID"),
    x_conversation_id: Optional[str] = Header(
        default=None, alias="X-Conversation-ID"
    ),
):
    _auth_or_401(authorization)
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc
    try:
        parsed = parse_chat_completion_request(
            body,
            user_id_header=x_user_id,
            conversation_id_header=x_conversation_id,
        )
    except BadRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    graph = get_rag_graph()

    if parsed.stream:
        chunks = astream_web_openai_events(graph, parsed)
        return StreamingResponse(
            format_sse_stream(chunks),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        payload = await complete_web_openai_response(graph, parsed)
    except Exception as exc:
        logger.exception("Non-stream chat completion failed")
        raise HTTPException(status_code=500, detail="RAG turn failed") from exc
    return JSONResponse(payload)


def main() -> None:
    import uvicorn

    host = os.environ.get("RAG_WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("RAG_WEB_PORT", "8081"))
    uvicorn.run(
        "web.app:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
