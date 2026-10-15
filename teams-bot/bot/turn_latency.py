"""Per-turn latency rows for Application Insights (same trace_id as RAG audit invocation_id).

Each log line: ``TEAMS_TURN_LATENCY`` + JSON. Query with ``scripts/kql/turn_latency_by_trace.kql``.

- ``elapsed_ms``: wall time from turn start (always comparable across steps).
- ``segment_ms``: duration of that *phase* (optimize / retrieve / respond).
  Older traces may include ``deep_agent_outer_stream_*`` from the removed outer Deep Agent path.
"""

from __future__ import annotations

import contextvars
import json
import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator, Optional

LATENCY_EVENT = "TEAMS_TURN_LATENCY"

_current: contextvars.ContextVar[TurnLatencyRecorder | None] = contextvars.ContextVar(
    "teams_turn_latency_recorder",
    default=None,
)


def current_turn_latency() -> TurnLatencyRecorder | None:
    return _current.get()


class TurnLatencyRecorder:
    def __init__(self, trace_id: str, logger: logging.Logger) -> None:
        self.trace_id = trace_id
        self._logger = logger
        self._t0 = time.perf_counter()
        # When inner_rag_respond_complete fires (inner tool returning to outer agent).
        self._inner_rag_tool_return_perf: Optional[float] = None

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._t0) * 1000

    def note_inner_rag_tool_returned(self) -> None:
        """Call once inner ``search_company_knowledge`` pipeline has emitted ``inner_rag_respond_complete``."""
        self._inner_rag_tool_return_perf = time.perf_counter()

    def outer_stream_tail_after_inner_ms(self) -> Optional[float]:
        """Wall ms from inner tool return to *now*; ``None`` if the tool did not complete this turn."""
        if self._inner_rag_tool_return_perf is None:
            return None
        return (time.perf_counter() - self._inner_rag_tool_return_perf) * 1000

    def emit(self, step: str, **fields: Any) -> None:
        payload: dict[str, Any] = {
            "event": LATENCY_EVENT,
            "trace_id": self.trace_id,
            "step": step,
            "elapsed_ms": round(self.elapsed_ms(), 2),
        }
        for key, value in fields.items():
            if value is not None:
                payload[key] = value
        line = json.dumps(payload, ensure_ascii=False)
        self._logger.info("%s %s", LATENCY_EVENT, line)


@contextmanager
def turn_latency_scope(trace_id: str, logger: logging.Logger) -> Iterator[TurnLatencyRecorder]:
    resolved_id = trace_id.strip() if trace_id else ""
    if not resolved_id:
        resolved_id = "no-azure-invocation-id"
    recorder = TurnLatencyRecorder(resolved_id, logger)
    token = _current.set(recorder)
    try:
        yield recorder
    finally:
        _current.reset(token)
