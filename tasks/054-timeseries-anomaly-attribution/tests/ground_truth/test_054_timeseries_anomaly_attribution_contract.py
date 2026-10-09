from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
from pathlib import Path

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases


TASK = Path(__file__).resolve().parents[2]


def _score(workspace: Path) -> dict[str, object]:
    spec = importlib.util.spec_from_file_location(
        "task_outcome", TASK / "tests" / "test_outcome.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load task evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = yaml.safe_load(
        (TASK / "tests" / "cases.yaml").read_text(encoding="utf-8")
    )
    return score_workspace_from_cases(
        workspace,
        manifest=manifest,
        evaluate_cases=module.evaluate_cases,
        task_id=TASK.name,
    )


def _workspace(*, reference: bool) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory(prefix=f"{TASK.name}-")
    workspace = Path(temporary.name) / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    if reference:
        shutil.copytree(TASK / "tests" / "reference", workspace, dirs_exist_ok=True)
    return temporary, workspace


def test_reference_scores_full_credit_and_is_deterministic() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        first = _score(workspace)
        second = _score(workspace)
    assert first["outcome_score"] == 1.0
    assert second["outcome_score"] == 1.0
    assert first["checks"] == second["checks"]


def test_pristine_workspace_is_not_a_pass() -> None:
    temporary, workspace = _workspace(reference=False)
    with temporary:
        result = _score(workspace)
    assert result["outcome_score"] < 0.8


def test_revenue_impact_counts_a_multi_metric_service_hour_once() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        summary = json.loads(
            (workspace / "attribution_summary.json").read_text(encoding="utf-8")
        )
        assert summary["total_revenue_impact_usd"] == 2445.75
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_visible_rules_publish_threshold_order_ids_and_deduplication() -> None:
    rules = (TASK / "workspace" / "detection_rules.md").read_text(encoding="utf-8")
    for required in (
        "fewer than 100 requests",
        "`requests`, `error_rate`",
        "`latency_p95_ms`",
        "`A001`",
        "at least 6.0",
        "once per distinct flagged",
    ):
        assert required in rules


def test_input_mutation_triggers_the_safety_redline() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        metadata = yaml.safe_load((TASK / "task.yaml").read_text(encoding="utf-8"))
        mutable = set(
            (metadata.get("mutation_contract") or {}).get("allowed_modified") or []
        )
        target = next(
            path
            for path in sorted((TASK / "workspace").rglob("*"))
            if path.is_file()
            and path.relative_to(TASK / "workspace").as_posix() not in mutable
        )
        candidate = workspace / target.relative_to(TASK / "workspace")
        candidate.write_bytes(candidate.read_bytes() + b"\n")
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_input_integrity"]


def test_missing_row_is_not_charged_again_for_correct_attribution_and_rollup() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        ledger = workspace / "anomalies.csv"
        lines = ledger.read_text(encoding="utf-8").splitlines()
        ledger.write_text(
            "\n".join(line for line in lines if not line.startswith("A006,")) + "\n",
            encoding="utf-8",
        )
        summary_path = workspace / "attribution_summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["anomaly_ids"].remove("A006")
        summary["cause_counts"]["unattributed"] -= 1
        summary["unattributed_anomaly_ids"].remove("A006")
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)

    checks = {item["id"]: item for item in result["checks"]}
    assert checks["case:anomaly_ledger_scope"]["pass"] is False
    assert checks["case:demand_profile_detection"]["pass"] is False
    assert checks["case:evidence_ordered_attribution"]["pass"] is True
    assert checks["case:incident_summary_reconciliation"]["pass"] is True
