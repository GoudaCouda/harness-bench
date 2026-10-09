from __future__ import annotations

import json
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import yaml

ROOT = Path(__file__).resolve().parents[1]
MAINTENANCE = ROOT / "tools" / "task_maintenance"
if str(MAINTENANCE) not in sys.path:
    sys.path.insert(0, str(MAINTENANCE))

from common import score_task_workspace  # noqa: E402
from validate_oracle_quality import make_workspace  # noqa: E402

TASK_ID = "023-oauth-refresh-race-recovery"


@contextmanager
def _reference_workspace() -> Iterator[tuple[Path, Path, dict]]:
    task = ROOT / "tasks" / TASK_ID
    metadata = yaml.safe_load((task / "task.yaml").read_text(encoding="utf-8"))
    workspace, cleanup_roots = make_workspace(task, metadata, "reference")
    try:
        yield workspace, task, metadata
    finally:
        for root in cleanup_roots:
            shutil.rmtree(root, ignore_errors=True)


def _mutate(old: str, new: str) -> dict:
    with _reference_workspace() as (workspace, task, metadata):
        path = workspace / "repo/src/refresh_recovery.py"
        source = path.read_text(encoding="utf-8")
        assert old in source
        path.write_text(source.replace(old, new, 1), encoding="utf-8")
        return score_task_workspace(task, metadata, workspace)


def test_023_reference_solution_passes() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        result = score_task_workspace(task, metadata, workspace)
    assert result["outcome_score"] == 1.0
    assert result["task_success"] is True


def test_023_detects_input_order_winner() -> None:
    result = _mutate(
        'sorted([(item["sequence"], item) for item in attempts])',
        '[(item["sequence"], item) for item in attempts]',
    )
    assert result["outcome_score"] < 1.0
    assert "visible_reconciliation_report" in result["failed_core_cases"]


def test_023_detects_stale_generation_overwrite() -> None:
    result = _mutate('item["observed_generation"] < generation', 'item["observed_generation"] < generation - 1')
    assert result["outcome_score"] < 1.0
    assert "winner_and_generation_behavior" in result["failed_core_cases"]


def test_023_detects_invalid_grant_retry() -> None:
    result = _mutate('response["error"] == "invalid_grant" and winner is None', 'False')
    assert result["outcome_score"] < 1.0
    assert "visible_reconciliation_report" in result["failed_core_cases"]


def test_023_detects_scope_escalation() -> None:
    result = _mutate('if not set(response["scope"]).issubset(set(session["scope"])):', 'if False:')
    assert result["outcome_score"] < 1.0
    assert "visible_reconciliation_report" in result["failed_core_cases"]


def test_023_detects_report_corruption() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        path = workspace / "repo/reconciliation_report.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        report[0]["reconciliation"]["winner_request_id"] = "wrong"
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        result = score_task_workspace(task, metadata, workspace)
    assert result["outcome_score"] == 0.9
    assert result["task_success"] is False
    assert result["failed_core_cases"] == ["visible_reconciliation_report"]
