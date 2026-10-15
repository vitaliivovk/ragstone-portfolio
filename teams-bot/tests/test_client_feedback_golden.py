"""
Golden-set checks for Client feedback (May 2026).

Loads ``teams-bot/logs/client_feedback_golden.txt`` and runs deterministic
composer-block checks (optimizer-driven answer_topic / numeric_answer_first).

Manual full repro (optimizer + retrieve + answer) from repo root::

    cd teams-bot
    python scripts/run_local_rag_tests.py --questions-file logs/client_feedback_golden.txt

Requires local.settings.json with OpenAI + Pinecone credentials.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rag.answer_composer import build_topic_composer_block

_GOLDEN_PATH = Path(__file__).resolve().parent.parent / "logs" / "client_feedback_golden.txt"

# Expected optimizer outputs (answer_topic, numeric_answer_first) per feedback id.
_EXPECTED_COMPOSER: dict[str, tuple[str, bool]] = {
    "A3": ("verification", False),
    "A4": ("early_termination", True),
    "A6": ("early_termination", True),
    "A7": ("verification", False),
    "A15": ("verification", False),
    "A16": ("early_termination", True),
    "A17": ("early_termination", True),
    "A18": ("verification", True),
}


def _load_golden_cases() -> list[tuple[str, str]]:
    if not _GOLDEN_PATH.is_file():
        pytest.skip(f"golden file missing: {_GOLDEN_PATH}")
    cases: list[tuple[str, str]] = []
    for line in _GOLDEN_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        issue_id, _, question = stripped.partition("\t")
        issue_id = issue_id.strip()
        question = question.strip()
        if issue_id and question:
            cases.append((issue_id, question))
    if not cases:
        pytest.skip("no golden cases parsed")
    return cases


_GOLDEN_CASES = _load_golden_cases()


@pytest.mark.parametrize("issue_id,question", _GOLDEN_CASES, ids=[c[0] for c in _GOLDEN_CASES])
def test_golden_composer_block_when_expected(issue_id: str, question: str) -> None:
    expected = _EXPECTED_COMPOSER.get(issue_id)
    if expected is None:
        pytest.skip(f"no composer expectation for {issue_id}")
    answer_topic, numeric_first = expected
    block = build_topic_composer_block(answer_topic, numeric_first)
    assert block.strip()
    if answer_topic == "verification":
        assert "weryfikac" in block.lower()
    elif answer_topic == "early_termination":
        assert "wcześniejsz" in block.lower() or "wczesniejsz" in block.lower()
    elif answer_topic == "deposit_kaucja":
        assert "kaucja" in block.lower()
    if numeric_first:
        assert "Zdanie otwierające" in block


def test_golden_file_has_nineteen_issues() -> None:
    assert len(_GOLDEN_CASES) == 19
