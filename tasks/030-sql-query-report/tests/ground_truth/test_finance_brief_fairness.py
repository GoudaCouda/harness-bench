from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


TASK = Path(__file__).resolve().parents[2]


def _load_evaluator():
    path = TASK / "tests" / "test_outcome.py"
    spec = importlib.util.spec_from_file_location("task_030_outcome", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load task 030 evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _frozen_gemma_brief() -> str:
    return (TASK / "tests" / "ground_truth" / "frozen_gemma_8k_brief.md").read_text(
        encoding="utf-8"
    )


def test_frozen_gemma_brief_accepts_leader_identity_without_unrequested_amounts() -> (
    None
):
    evaluator = _load_evaluator()
    brief = _frozen_gemma_brief()

    assert "4,385" not in brief
    assert "7,525" not in brief
    assert evaluator._brief_is_complete(brief, sql_executed=True) is True


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("16,750.00", "16,751.00"),
        ("Atlas Laptop (P101)", "Boreal Monitor (P999)"),
        ("**Leading Region:** North", "**Leading Region:** West"),
        ("**Included Orders:** 19", "**Included Orders:** 18"),
        ("6 (Status)", "7 (Status)"),
        ("5 (Date)", "4 (Date)"),
        ("Gross Revenue | 18,075.00", "Gross Revenue | 18,000.00"),
        ("`partially_refunded`", "`partially_refund_pending`"),
        (
            "There were no material ties in the product or region leaderboards for this snapshot.",
            "The product and region leaderboards were reviewed.",
        ),
    ],
)
def test_frozen_gemma_brief_still_requires_every_published_handoff_claim(
    old: str, new: str
) -> None:
    evaluator = _load_evaluator()
    brief = _frozen_gemma_brief()

    assert old in brief
    assert (
        evaluator._brief_is_complete(brief.replace(old, new), sql_executed=True)
        is False
    )


def test_brief_cannot_self_attest_when_sql_did_not_execute() -> None:
    evaluator = _load_evaluator()

    assert (
        evaluator._brief_is_complete(_frozen_gemma_brief(), sql_executed=False) is False
    )
