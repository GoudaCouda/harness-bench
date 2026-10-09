from __future__ import annotations

import csv
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


TASK_ID = "054-timeseries-anomaly-attribution"


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


def _read_anomalies(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write_anomalies(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def test_054_one_critical_measurement_does_not_erase_other_signals() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        path = workspace / "anomalies.csv"
        header, rows = _read_anomalies(path)
        next(row for row in rows if row["anomaly_id"] == "A001")["observed"] = "0.0838"
        _write_anomalies(path, header, rows)
        result = score_task_workspace(task, metadata, workspace)

    checks = {
        str(check["id"]).removeprefix("case:"): check for check in result["checks"]
    }
    assert result["outcome_score"] == 0.85
    assert result["task_success"] is False
    assert result["failed_core_cases"] == ["critical_service_detection"]
    assert checks["demand_profile_detection"]["pass"] is True


def test_054_consistent_wrong_cause_is_charged_once() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        anomaly_path = workspace / "anomalies.csv"
        header, rows = _read_anomalies(anomaly_path)
        next(row for row in rows if row["anomaly_id"] == "A005")["attributed_cause"] = (
            "deployment:D-999"
        )
        _write_anomalies(anomaly_path, header, rows)

        summary_path = workspace / "attribution_summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["cause_counts"]["deployment"] = 3
        summary["cause_counts"]["unattributed"] = 1
        summary["unattributed_anomaly_ids"] = ["A006"]
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        result = score_task_workspace(task, metadata, workspace)

    checks = {
        str(check["id"]).removeprefix("case:"): check for check in result["checks"]
    }
    assert result["outcome_score"] == 0.8
    assert result["task_success"] is False
    assert result["failed_core_cases"] == ["evidence_ordered_attribution"]
    assert checks["incident_summary_reconciliation"]["pass"] is True
    assert checks["impact_accounting"]["pass"] is True


def test_054_high_severity_summary_is_recomputed_from_submitted_rows() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        summary_path = workspace / "attribution_summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["high_severity_count"] = 4
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        result = score_task_workspace(task, metadata, workspace)

    assert result["outcome_score"] == 0.8
    assert result["task_success"] is False
    assert result["failed_core_cases"] == ["incident_summary_reconciliation"]


def test_054_partial_ledger_loses_scope_but_keeps_correct_row_attribution() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        path = workspace / "anomalies.csv"
        header, rows = _read_anomalies(path)
        _write_anomalies(path, header, rows[:1])
        result = score_task_workspace(task, metadata, workspace)

    checks = {
        str(check["id"]).removeprefix("case:"): check for check in result["checks"]
    }
    assert checks["anomaly_ledger_scope"]["pass"] is False
    assert checks["evidence_ordered_attribution"]["pass"] is True
    assert checks["incident_summary_reconciliation"]["pass"] is False
