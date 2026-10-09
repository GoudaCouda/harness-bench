from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
ORACLE_PATH = Path(__file__).with_name("oracle_impl.py")
REFERENCE = TASK / "tests" / "reference" / "review_findings.json"


def _load_oracle():
    spec = importlib.util.spec_from_file_location("oracle_026", ORACLE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ORACLE = _load_oracle()


def _workspace(tmp_path: Path, mutate=None) -> Path:
    workspace = tmp_path / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    report = json.loads(REFERENCE.read_text(encoding="utf-8"))
    if mutate:
        mutate(report)
    (workspace / "review_findings.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return workspace


def _checks(result: dict) -> dict[str, dict]:
    return {check["id"]: check for check in result["checks"]}


def test_reference_scores_one(tmp_path: Path) -> None:
    result = ORACLE.score_workspace(_workspace(tmp_path))
    assert result["outcome_score"] == 1.0
    assert all(check["pass"] for check in result["checks"])


def test_missing_zero_ttl_loses_only_data_lifecycle_cluster(tmp_path: Path) -> None:
    def mutate(report: dict) -> None:
        report["findings"] = [
            item
            for item in report["findings"]
            if item["id"] != "zero-ttl"
        ]

    result = ORACLE.score_workspace(_workspace(tmp_path, mutate))
    checks = _checks(result)
    assert result["outcome_score"] == 0.80
    assert not checks["data_lifecycle_review"]["pass"]
    assert checks["prioritization_and_verification"]["pass"]
    assert checks["report_integrity"]["pass"]


def test_missing_tenant_idempotency_loses_authorization_cluster_once(tmp_path: Path) -> None:
    def mutate(report: dict) -> None:
        report["findings"] = [
            item
            for item in report["findings"]
            if item["id"] != "tenant-idempotency"
        ]

    result = ORACLE.score_workspace(_workspace(tmp_path, mutate))
    checks = _checks(result)
    assert result["outcome_score"] == 0.70
    assert not checks["authorization_and_tenant_review"]["pass"]
    assert checks["prioritization_and_verification"]["pass"]


def test_wrong_severity_loses_quality_not_finding_cluster(tmp_path: Path) -> None:
    def mutate(report: dict) -> None:
        next(item for item in report["findings"] if item["id"] == "atomic-claim")[
            "severity"
        ] = "medium"

    result = ORACLE.score_workspace(_workspace(tmp_path, mutate))
    checks = _checks(result)
    assert result["outcome_score"] == 0.90
    assert checks["worker_state_review"]["pass"]
    assert not checks["prioritization_and_verification"]["pass"]


def test_hidden_finding_count_is_not_a_shape_requirement(tmp_path: Path) -> None:
    def mutate(report: dict) -> None:
        report["findings"] = report["findings"][:1]

    result = ORACLE.score_workspace(_workspace(tmp_path, mutate))
    assert _checks(result)["report_integrity"]["pass"]


def test_fixture_mutation_zeroes_score(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    (workspace / "review" / "diff.patch").write_text("changed", encoding="utf-8")
    result = ORACLE.score_workspace(workspace)
    assert result["outcome_score"] == 0.0
    assert not _checks(result)["fixture_integrity"]["pass"]
