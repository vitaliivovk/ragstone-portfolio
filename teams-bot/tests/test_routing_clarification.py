"""Graph routing when optimizer requests clarification."""

from rag.graph import route_after_optimize


def test_route_after_optimize_clarify_before_rag() -> None:
    state = {
        "clarification_needed": True,
        "needs_rag": True,
    }
    assert route_after_optimize(state) == "respond_clarify"


def test_route_after_optimize_retrieve_when_no_clarify() -> None:
    state = {
        "clarification_needed": False,
        "needs_rag": True,
    }
    assert route_after_optimize(state) == "retrieve"
