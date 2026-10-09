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


TASK_ID = "019-wheel-install-transaction-recovery"


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


def _mutate_source(old: str, new: str) -> dict:
    with _reference_workspace() as (workspace, task, metadata):
        path = workspace / "repo/src/install_recovery.py"
        source = path.read_text(encoding="utf-8")
        assert old in source
        path.write_text(source.replace(old, new, 1), encoding="utf-8")
        return score_task_workspace(task, metadata, workspace)


def test_019_reference_solution_passes() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        result = score_task_workspace(task, metadata, workspace)
    assert result["outcome_score"] == 1.0
    assert result["task_success"] is True


def test_019_detects_forward_rollback_order() -> None:
    result = _mutate_source(
        "range(len(entries) - 1, -1, -1)",
        "range(0, len(entries), 1)",
    )
    assert result["outcome_score"] < 1.0
    assert "transaction_rollback_behavior" in result["failed_core_cases"]


def test_019_detects_shared_owner_omission() -> None:
    result = _mutate_source(
        'elif package not in before["owners"]:',
        "elif False:",
    )
    assert result["outcome_score"] < 1.0
    assert "shared_drift_and_retry_edges" in result["failed_core_cases"]


def test_019_detects_non_atomic_drift_recovery() -> None:
    result = _mutate_source(
        '{"decision": "manual_intervention", "actions": [], "conflicts": conflicts}',
        '{"decision": "manual_intervention", "actions": actions, "conflicts": conflicts}',
    )
    assert result["outcome_score"] < 1.0
    assert "shared_drift_and_retry_edges" in result["failed_core_cases"]


def test_019_detects_record_digest_mismatch() -> None:
    result = _mutate_source(
        'entry["after_digest"] != records[path]["digest"]',
        "False",
    )
    assert result["outcome_score"] < 1.0
    assert "shared_drift_and_retry_edges" in result["failed_core_cases"]


def test_019_detects_visible_report_corruption() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        path = workspace / "repo/recovery_report.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        report[0]["plan"]["decision"] = "manual_intervention"
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        result = score_task_workspace(task, metadata, workspace)
    assert result["outcome_score"] == 0.9
    assert result["task_success"] is False
    assert result["failed_core_cases"] == ["visible_recovery_report"]
