"""Unit tests for the OpenAI-compatible web adapter (request parse, SSE, auth)."""

from __future__ import annotations

import json
import os

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from web.openai_compat import (
    AuthError,
    BadRequestError,
    REASONING_KEY,
    append_sources_markdown,
    chat_completion_chunk,
    map_openai_messages_to_history,
    models_list_payload,
    parse_chat_completion_request,
    require_bearer_api_key,
    sse_data_line,
)


def test_map_messages_history_and_current_user() -> None:
    history, current = map_openai_messages_to_history(
        [
            {"role": "system", "content": "ignore me"},
            {"role": "user", "content": "Pierwsze pytanie"},
            {"role": "assistant", "content": "Pierwsza odpowiedź"},
            {"role": "user", "content": "Drugie pytanie"},
        ]
    )
    assert current == "Drugie pytanie"
    assert len(history) == 2
    assert isinstance(history[0], HumanMessage)
    assert history[0].content == "Pierwsze pytanie"
    assert isinstance(history[1], AIMessage)
    assert history[1].content == "Pierwsza odpowiedź"


def test_map_messages_rejects_empty_and_non_user_last() -> None:
    with pytest.raises(BadRequestError):
        map_openai_messages_to_history([])
    with pytest.raises(BadRequestError):
        map_openai_messages_to_history(
            [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
        )
    with pytest.raises(BadRequestError):
        map_openai_messages_to_history([{"role": "user", "content": "   "}])


def test_map_messages_multipart_content() -> None:
    history, current = map_openai_messages_to_history(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Część "},
                    {"type": "text", "text": "A"},
                ],
            }
        ]
    )
    assert history == []
    assert current == "Część A"


def test_parse_chat_completion_reads_headers() -> None:
    req = parse_chat_completion_request(
        {
            "model": "ragstone",
            "stream": True,
            "messages": [{"role": "user", "content": "Hej"}],
        },
        user_id_header="entra-oid-1",
        conversation_id_header="conv-99",
    )
    assert req.user_id == "entra-oid-1"
    assert req.conversation_id == "conv-99"
    assert req.stream is True
    assert req.user_message == "Hej"
    assert req.history == []


def test_require_bearer_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAG_WEB_API_KEY", raising=False)
    require_bearer_api_key(None)  # auth disabled when unset

    monkeypatch.setenv("RAG_WEB_API_KEY", "secret-key")
    with pytest.raises(AuthError):
        require_bearer_api_key(None)
    with pytest.raises(AuthError):
        require_bearer_api_key("Bearer wrong")
    require_bearer_api_key("Bearer secret-key")
    require_bearer_api_key("secret-key")


def test_sse_chunk_format_includes_reasoning_key() -> None:
    chunk = chat_completion_chunk(
        completion_id="chatcmpl-test",
        model="ragstone",
        created=1,
        role="assistant",
        reasoning_content="Analizuję pytanie…",
    )
    assert chunk["object"] == "chat.completion.chunk"
    delta = chunk["choices"][0]["delta"]
    assert delta["role"] == "assistant"
    assert delta[REASONING_KEY] == "Analizuję pytanie…"
    line = sse_data_line(chunk)
    assert line.startswith("data: ")
    assert line.endswith("\n\n")
    parsed = json.loads(line[len("data: ") :].strip())
    assert parsed["choices"][0]["delta"][REASONING_KEY] == "Analizuję pytanie…"


def test_models_list_payload() -> None:
    payload = models_list_payload(model_id="ragstone")
    assert payload["object"] == "list"
    assert payload["data"][0]["id"] == "ragstone"


def test_append_sources_markdown(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_format(rows: list) -> str:
        return "1. doc.pdf"

    monkeypatch.setattr(
        "rag.citations.format_citations_from_display_rows",
        _fake_format,
    )
    monkeypatch.setattr(
        "rag.citations.should_attach_source_block",
        lambda _t: True,
    )
    out = append_sources_markdown(
        "Odpowiedź.",
        display_rows=[{"fileName": "doc.pdf"}],
        attach_sources_block=True,
    )
    assert "Odpowiedź." in out
    assert "**Źródła:**" in out
    assert "1. doc.pdf" in out


@pytest.mark.asyncio
async def test_app_auth_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    """FastAPI route rejects bad bearer without touching RAG graph."""
    from fastapi.testclient import TestClient

    monkeypatch.setenv("RAG_WEB_API_KEY", "expected")
    # Avoid lazy graph init on import path for models list — still needs auth first.
    from web import app as web_app

    client = TestClient(web_app.app)
    resp = client.get("/v1/models")
    assert resp.status_code == 401
    resp_ok = client.get(
        "/v1/models",
        headers={"Authorization": "Bearer expected"},
    )
    assert resp_ok.status_code == 200
    assert resp_ok.json()["data"][0]["id"] in ("ragstone", os.environ.get("RAG_WEB_MODEL_ID", "ragstone"))


@pytest.mark.asyncio
async def test_chat_completions_bad_body(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    monkeypatch.setenv("RAG_WEB_API_KEY", "expected")
    from web import app as web_app

    client = TestClient(web_app.app)
    resp = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer expected"},
        json={"messages": []},
    )
    assert resp.status_code == 400
