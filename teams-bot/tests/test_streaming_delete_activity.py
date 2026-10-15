"""Tests for ``TeamsStreamer.delete_stream_activity`` recovery from broken streams.

The Bot Framework returns 403 ``ContentStreamNotAllowed`` when a streamed chunk (or
final activity) does not strictly extend the previous text — typically when our
post-processed answer renumbers ``[Źródło N]`` tags after the LLM has already
streamed the raw model numbering. To avoid showing the user *both* the broken
partial bubble **and** the clean fallback message, the orchestrator deletes the
partial via ``DELETE /v3/conversations/{convId}/activities/{activityId}`` before
shipping the authoritative answer with ``send_message``.
"""
from __future__ import annotations

from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.streaming import StreamState, TeamsStreamer


class _FakeResponse:
    def __init__(self, status: int, body: str = "") -> None:
        self.status = status
        self._body = body

    async def text(self) -> str:
        return self._body

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


def _make_streamer(
    *,
    stream_id: Optional[str],
    is_group_chat: bool = False,
    delete_response: Optional[_FakeResponse] = None,
    delete_raises: Optional[Exception] = None,
) -> tuple[TeamsStreamer, MagicMock]:
    activity = MagicMock()
    activity.service_url = "https://smba.example.com/teams/"
    activity.conversation_id = "19:abc@thread.skype"
    activity.is_group_chat = is_group_chat
    activity.raw_activity = {
        "recipient": {"id": "bot"},
        "from": {"id": "user"},
        "conversation": {"id": "19:abc@thread.skype"},
    }

    streamer = TeamsStreamer(
        activity=activity,
        app_id="app",
        app_password="secret",
    )
    streamer.state = StreamState(stream_id=stream_id, is_active=True)
    streamer._token = "test-token"
    streamer._token_expires = 9_999_999_999

    session = MagicMock()
    if delete_raises is not None:
        session.delete = MagicMock(side_effect=delete_raises)
    else:
        session.delete = MagicMock(return_value=delete_response)
    streamer._session = session  # type: ignore[assignment]
    return streamer, session


@pytest.mark.asyncio
async def test_delete_stream_activity_returns_false_without_stream_id() -> None:
    streamer, session = _make_streamer(stream_id=None)
    assert await streamer.delete_stream_activity() is False
    session.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_stream_activity_skips_in_group_chat() -> None:
    streamer, session = _make_streamer(
        stream_id="activity-123", is_group_chat=True
    )
    assert await streamer.delete_stream_activity() is False
    session.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_stream_activity_returns_true_on_202() -> None:
    streamer, session = _make_streamer(
        stream_id="activity-123",
        delete_response=_FakeResponse(status=202),
    )
    assert await streamer.delete_stream_activity() is True
    assert streamer.state.is_active is False
    session.delete.assert_called_once()
    called_url = session.delete.call_args[0][0]
    assert "/v3/conversations/" in called_url
    assert called_url.endswith("/activities/activity-123")


@pytest.mark.asyncio
async def test_delete_stream_activity_returns_true_on_200_and_204() -> None:
    for status in (200, 204):
        streamer, _session = _make_streamer(
            stream_id="activity-xyz",
            delete_response=_FakeResponse(status=status),
        )
        assert await streamer.delete_stream_activity() is True
        assert streamer.state.is_active is False


@pytest.mark.asyncio
async def test_delete_stream_activity_returns_false_on_404() -> None:
    streamer, _session = _make_streamer(
        stream_id="activity-404",
        delete_response=_FakeResponse(status=404, body='{"error":"missing"}'),
    )
    assert await streamer.delete_stream_activity() is False
    # Best-effort: leave is_active alone on failure so the caller's behaviour is
    # not affected by a partial cleanup.
    assert streamer.state.is_active is True


@pytest.mark.asyncio
async def test_delete_stream_activity_returns_false_when_session_raises() -> None:
    streamer, _session = _make_streamer(
        stream_id="activity-boom",
        delete_raises=RuntimeError("network down"),
    )
    assert await streamer.delete_stream_activity() is False
    assert streamer.state.is_active is True


@pytest.mark.asyncio
async def test_delete_stream_activity_uses_quoted_conversation_id() -> None:
    streamer, session = _make_streamer(
        stream_id="activity-456",
        delete_response=_FakeResponse(status=200),
    )
    streamer.activity.conversation_id = "19:abc def@thread.skype"
    assert await streamer.delete_stream_activity() is True
    called_url = session.delete.call_args[0][0]
    # ":", " " and "@" inside the conversation id must be percent-encoded so the
    # path is well formed. ``urllib.parse.quote`` keeps "/" unquoted by default,
    # which matches the existing ``_send_activity`` URL building.
    assert "19%3Aabc%20def%40thread.skype" in called_url
    assert called_url.endswith("/activities/activity-456")
