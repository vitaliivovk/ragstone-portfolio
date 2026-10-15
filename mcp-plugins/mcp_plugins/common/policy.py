"""Server-enforced tool scope policy (TASKS #14).

v1 never allows live send/post. Draft may be enabled per plugin later.
"""

from __future__ import annotations

from enum import Enum
from typing import FrozenSet, Mapping


class ToolScope(str, Enum):
    READ = "read"
    SEARCH = "search"
    DRAFT = "draft"
    SEND = "send"  # outbound delivery — denied in v1


# Conservative defaults for Office IDE Phase 3+.
V1_DEFAULT_POLICY: FrozenSet[ToolScope] = frozenset(
    {
        ToolScope.READ,
        ToolScope.SEARCH,
        ToolScope.DRAFT,
    }
)


class ScopeDenied(PermissionError):
    """Raised when a tool's scope is not in the active policy."""

    def __init__(self, tool: str, scope: ToolScope, *, reason: str = "scope_denied") -> None:
        self.tool = tool
        self.scope = scope
        self.reason = reason
        super().__init__(f"tool {tool!r} scope {scope.value!r} denied ({reason})")


def enforce_scope(
    tool: str,
    scope: ToolScope,
    allowed: FrozenSet[ToolScope] | None = None,
) -> None:
    """Raise ScopeDenied if scope is not permitted.

    SEND is always rejected in v1 even if a caller widens the set by mistake.
    """
    policy = V1_DEFAULT_POLICY if allowed is None else allowed
    if scope is ToolScope.SEND:
        raise ScopeDenied(tool, scope, reason="never_send_v1")
    if scope not in policy:
        raise ScopeDenied(tool, scope, reason="scope_denied")


def resolve_tool_scope(
    tool_name: str,
    catalog: Mapping[str, ToolScope],
) -> ToolScope:
    """Look up the declared scope for a tool; unknown tools are denied as SEND."""
    if tool_name not in catalog:
        raise ScopeDenied(tool_name, ToolScope.SEND, reason="unknown_tool")
    return catalog[tool_name]
