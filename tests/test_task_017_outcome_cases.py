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


TASK_ID = "017-http-cache-revalidation"


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
        path = workspace / "repo/src/cache_revalidation.py"
        source = path.read_text(encoding="utf-8")
        assert old in source
        path.write_text(source.replace(old, new, 1), encoding="utf-8")
        return score_task_workspace(task, metadata, workspace)


def test_017_reference_solution_passes() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        result = score_task_workspace(task, metadata, workspace)
    assert result["outcome_score"] == 1.0
    assert result["task_success"] is True


def test_017_detects_strong_only_etag_comparison() -> None:
    result = _mutate_source(
        'if value.startswith("W/"):',
        'if value.startswith("never-W/"):',
    )
    assert result["outcome_score"] < 1.0
    assert "validator_and_variant_behavior" in result["failed_core_cases"]


def test_017_detects_vary_omission() -> None:
    result = _mutate_source(
        'if request["headers"].get(name, "").strip() != stored["request_headers"].get(name, "").strip():',
        'if False:',
    )
    assert result["outcome_score"] < 1.0
    assert "validator_and_variant_behavior" in result["failed_core_cases"]


def test_017_detects_exact_date_boundary_error() -> None:
    result = _mutate_source("if modified <= requested:", "if modified < requested:")
    assert result["outcome_score"] < 1.0
    assert "validator_and_variant_behavior" in result["failed_core_cases"]


def test_017_detects_visible_report_corruption() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        path = workspace / "repo/revalidation_report.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        report[0]["decision"]["reason"] = "etag_miss"
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        result = score_task_workspace(task, metadata, workspace)
    assert result["outcome_score"] == 0.9
    assert result["task_success"] is False
    assert result["failed_core_cases"] == ["visible_revalidation_report"]
