# Hosting choice (Phase 1)

The OpenAI-compatible RAG adapter runs as a **FastAPI / uvicorn sidecar** (`teams-bot/web/app.py`), not as new Azure Functions routes.

**Why not Functions first:** reliable SSE (`text/event-stream`) and long-lived chat streams are awkward on the Azure Functions Python worker; a small ASGI app shares the same `rag/` code and env and can later deploy on Azure Container Apps next to LibreChat.

Teams remains on Functions unchanged.
