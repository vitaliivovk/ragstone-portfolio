"""OpenAI-compatible request helpers for the LibreChat web adapter."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

DEFAULT_MODEL_ID = "ragstone"
REASONING_KEY = "reasoning_content"


@dataclass(frozen=True)
class ChatCompletionRequest:
    """Parsed ``POST /v1/chat/completions`` body + identity headers."""

    model: str
    user_message: str
    history: list[BaseMessage]
    stream: bool
    user_id: str
    conversation_id: str


class AuthError(Exception):
    """Bearer API key missing or wrong."""


class BadRequestError(Exception):
    """Malformed OpenAI-compat payload."""


def expected_api_key() -> str:
    return (os.environ.get("RAG_WEB_API_KEY") or "").strip()


def require_bearer_api_key(authorization: Optional[str]) -> None:
    """
    Validate ``Authorization: Bearer <key>`` against ``RAG_WEB_API_KEY``.

    If ``RAG_WEB_API_KEY`` is unset/empty, auth is disabled (local spike only).
    """
    expected = expected_api_key()
    if not expected:
        return
    if not authorization or not str(authorization).strip():
        raise AuthError("Missing Authorization header")
    raw = str(authorization).strip()
    if raw.lower().startswith("bearer "):
        token = raw[7:].strip()
    else:
        token = raw
    if token != expected:
        raise AuthError("Invalid API key")


def _message_content_to_str(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                if part.get("type") == "text" and "text" in part:
                    parts.append(str(part["text"]))
                elif "text" in part:
                    parts.append(str(part["text"]))
        return "".join(parts)
    return str(content)


def map_openai_messages_to_history(
    messages: list[dict[str, Any]],
) -> tuple[list[BaseMessage], str]:
    """
    Map LibreChat / OpenAI chat messages to prior history + current user text.

    System messages are skipped (LibreChat may send them; our pipeline has its own prompts).
    The last ``user`` message is the current turn; earlier user/assistant pairs are history.
    """
    if not messages:
        raise BadRequestError("messages must be a non-empty list")

    normalized: list[tuple[str, str]] = []
    for raw in messages:
        if not isinstance(raw, dict):
            raise BadRequestError("each message must be an object")
        role = str(raw.get("role") or "").strip().lower()
        if role in ("system", "tool", "function"):
            continue
        if role not in ("user", "assistant"):
            raise BadRequestError(f"unsupported message role: {role or '(empty)'}")
        text = _message_content_to_str(raw.get("content")).strip()
        if not text and role == "assistant":
            continue
        normalized.append((role, text))

    if not normalized:
        raise BadRequestError("no user/assistant messages after filtering")

    last_role, last_text = normalized[-1]
    if last_role != "user":
        raise BadRequestError("last message must be from user")
    if not last_text:
        raise BadRequestError("user message content is empty")

    history: list[BaseMessage] = []
    for role, text in normalized[:-1]:
        if role == "user":
            history.append(HumanMessage(content=text))
        else:
            history.append(AIMessage(content=text))
    return history, last_text


def parse_chat_completion_request(
    body: dict[str, Any],
    *,
    user_id_header: Optional[str] = None,
    conversation_id_header: Optional[str] = None,
) -> ChatCompletionRequest:
    if not isinstance(body, dict):
        raise BadRequestError("JSON body must be an object")
    messages = body.get("messages")
    if not isinstance(messages, list):
        raise BadRequestError("messages must be a list")
    history, user_message = map_openai_messages_to_history(messages)
    model = str(body.get("model") or DEFAULT_MODEL_ID).strip() or DEFAULT_MODEL_ID
    stream = bool(body.get("stream", False))
    user_id = (user_id_header or "").strip() or str(body.get("user") or "").strip() or "web-anonymous"
    conversation_id = (conversation_id_header or "").strip()
    return ChatCompletionRequest(
        model=model,
        user_message=user_message,
        history=history,
        stream=stream,
        user_id=user_id,
        conversation_id=conversation_id,
    )


def models_list_payload(*, model_id: str = DEFAULT_MODEL_ID) -> dict[str, Any]:
    created = int(time.time())
    return {
        "object": "list",
        "data": [
            {
                "id": model_id,
                "object": "model",
                "created": created,
                "owned_by": "ragstone",
            }
        ],
    }


def new_completion_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex[:24]}"


def sse_data_line(payload: dict[str, Any]) -> str:
    import json

    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def chat_completion_chunk(
    *,
    completion_id: str,
    model: str,
    created: int,
    content: Optional[str] = None,
    reasoning_content: Optional[str] = None,
    role: Optional[str] = None,
    finish_reason: Optional[str] = None,
) -> dict[str, Any]:
    delta: dict[str, Any] = {}
    if role is not None:
        delta["role"] = role
    if reasoning_content is not None:
        delta[REASONING_KEY] = reasoning_content
    if content is not None:
        delta["content"] = content
    return {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
            }
        ],
    }


def chat_completion_response(
    *,
    completion_id: str,
    model: str,
    created: int,
    content: str,
) -> dict[str, Any]:
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def append_sources_markdown(
    answer: str,
    *,
    display_rows: list[dict],
    attach_sources_block: bool,
) -> str:
    """Append **Źródła** block when citations should be shown (Teams parity)."""
    from rag.citations import (
        format_citations_from_display_rows,
        should_attach_source_block,
    )

    body = (answer or "").strip()
    if not display_rows:
        return body
    if not (attach_sources_block or should_attach_source_block(body)):
        return body
    citations = format_citations_from_display_rows(display_rows)
    if not citations:
        return body
    block = f"**Źródła:**\n{citations}"
    if not body:
        return block
    return f"{body}\n\n{block}"
