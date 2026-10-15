"""Unit tests for scope policy helpers (no network)."""

from __future__ import annotations

import pytest

from mcp_plugins.common.policy import (
    V1_DEFAULT_POLICY,
    ScopeDenied,
    ToolScope,
    enforce_scope,
    resolve_tool_scope,
)


def test_v1_allows_read_search_draft() -> None:
    for scope in (ToolScope.READ, ToolScope.SEARCH, ToolScope.DRAFT):
        enforce_scope("demo", scope)


def test_v1_never_allows_send() -> None:
    with pytest.raises(ScopeDenied) as exc:
        enforce_scope("teams_post_message", ToolScope.SEND)
    assert exc.value.reason == "never_send_v1"


def test_send_denied_even_if_policy_widened() -> None:
    wide = frozenset({*V1_DEFAULT_POLICY, ToolScope.SEND})
    with pytest.raises(ScopeDenied) as exc:
        enforce_scope("x", ToolScope.SEND, wide)
    assert exc.value.reason == "never_send_v1"


def test_unknown_tool_denied() -> None:
    with pytest.raises(ScopeDenied) as exc:
        resolve_tool_scope("nope", {"sharepoint_read_file": ToolScope.READ})
    assert exc.value.reason == "unknown_tool"


def test_resolve_known_tool() -> None:
    assert resolve_tool_scope("sharepoint_read_file", {"sharepoint_read_file": ToolScope.READ}) is ToolScope.READ
