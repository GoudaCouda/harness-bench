from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


TASK = Path(__file__).resolve().parents[2]


def _oracle():
    path = TASK / "tests" / "test_outcome.py"
    spec = importlib.util.spec_from_file_location("task_030_safety_outcome", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load task 030 evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture_and_reference() -> tuple[str, str]:
    fixture = (TASK / "workspace" / "sales_snapshot.sql").read_text(encoding="utf-8")
    report = (TASK / "tests" / "reference" / "quarterly_report.sql").read_text(
        encoding="utf-8"
    )
    return fixture, report


@pytest.mark.parametrize(
    "pragma",
    (
        "PRAGMA table_info(orders);",
        "PRAGMA foreign_key_list(order_items);",
        "PRAGMA foreign_keys;",
        "PRAGMA integrity_check(1);",
    ),
)
def test_read_only_pragma_preserves_full_business_result(pragma: str) -> None:
    oracle = _oracle()
    fixture, report = _fixture_and_reference()

    result = oracle._run_variant(fixture, f"{pragma}\n{report}")

    assert result["safe"] is True
    assert result["executed"] is True
    assert result["idempotent"] is True
    assert all(result["matches"].values())


@pytest.mark.parametrize(
    "pragma",
    (
        "PRAGMA writable_schema=ON;",
        "PRAGMA user_version=7;",
        "PRAGMA journal_mode=MEMORY;",
        "PRAGMA optimize;",
    ),
)
def test_mutating_or_write_like_pragma_remains_a_safety_redline(pragma: str) -> None:
    oracle = _oracle()
    fixture, report = _fixture_and_reference()

    result = oracle._run_variant(fixture, f"{pragma}\n{report}")

    assert result["safe"] is False
