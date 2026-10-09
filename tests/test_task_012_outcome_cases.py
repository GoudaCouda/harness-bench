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


TASK_ID = "012-feature-flag-retirement"


@contextmanager
def _reference_workspace() -> Iterator[tuple[Path, Path, dict]]:
    task = ROOT / "tasks" / TASK_ID
    metadata = yaml.safe_load((task / "task.yaml").read_text(encoding="utf-8"))
    workspace, cleanup_roots = make_workspace(task, metadata, "reference")
    try:
        yield workspace, task, metadata
    finally:
        for cleanup_root in cleanup_roots:
            shutil.rmtree(cleanup_root, ignore_errors=True)


def test_012_reference_solution_passes_every_case() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        result = score_task_workspace(task, metadata, workspace)

    assert result["outcome_score"] == 1.0
    assert result["task_success"] is True
    assert result["failed_core_cases"] == []


def test_012_detects_receipt_time_regression() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        source_path = workspace / "repo/src/checkout_policy.py"
        source = source_path.read_text(encoding="utf-8")
        source_path.write_text(
            source.replace(
                'event_time = _timestamp(event["event_time"])',
                'event_time = _timestamp(event["received_at"])',
            ),
            encoding="utf-8",
        )
        result = score_task_workspace(task, metadata, workspace)

    assert result["outcome_score"] == 0.3
    assert result["task_success"] is False
    assert result["failed_core_cases"] == [
        "historical_and_retired_behavior",
        "fail_closed_replay_edges",
    ]


def test_012_detects_exact_cutoff_regression() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        source_path = workspace / "repo/src/checkout_policy.py"
        source = source_path.read_text(encoding="utf-8")
        source_path.write_text(
            source.replace("if event_time < retired_at:", "if event_time <= retired_at:"),
            encoding="utf-8",
        )
        result = score_task_workspace(task, metadata, workspace)

    assert result["outcome_score"] == 0.55
    assert result["task_success"] is False
    assert result["failed_core_cases"] == ["historical_and_retired_behavior"]


def test_012_detects_integer_boolean_regression() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        source_path = workspace / "repo/src/checkout_policy.py"
        source = source_path.read_text(encoding="utf-8")
        source_path.write_text(
            source.replace(
                "not isinstance(snapshot[flag], bool)",
                "not isinstance(snapshot[flag], (bool, int))",
            ),
            encoding="utf-8",
        )
        result = score_task_workspace(task, metadata, workspace)

    assert result["outcome_score"] == 0.75
    assert result["task_success"] is False
    assert result["failed_core_cases"] == ["fail_closed_replay_edges"]


def test_012_detects_unrelated_registry_deletion() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        registry_path = workspace / "repo/config/flags.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        del registry["flags"]["fraud_rules_v3"]
        registry_path.write_text(
            json.dumps(registry, indent=2) + "\n",
            encoding="utf-8",
        )
        result = score_task_workspace(task, metadata, workspace)

    assert result["outcome_score"] == 0.9
    assert result["task_success"] is False
    assert result["failed_core_cases"] == ["registry_retirement"]
