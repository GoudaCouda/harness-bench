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


def test_reference_scores_full_credit_deterministically() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        first = _score(workspace)
        second = _score(workspace)
    assert first["outcome_score"] == 1.0
    assert second["checks"] == first["checks"]


def test_equivalent_claim_decision_wording_is_accepted() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        path = workspace / "report_state.json"
        state = json.loads(path.read_text(encoding="utf-8"))
        state["claim_decisions"] = {
            "employment_increased": "refuted; corrected direction is decline",
            "average_hours_decreased": "retract; corrected direction is rise",
            "employment_above_january": "still valid",
        }
        path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_explicit_unknown_nsa_row_is_a_safe_equivalent() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        revisions = workspace / "revisions.csv"
        revisions.write_text(
            revisions.read_text(encoding="utf-8")
            + "EMP_NSA,2026-06,unknown,109,unknown,not_seasonally_adjusted\n",
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_nsa_row_with_invented_preliminary_value_is_rejected() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        revisions = workspace / "revisions.csv"
        revisions.write_text(
            revisions.read_text(encoding="utf-8")
            + "EMP_NSA,2026-06,108,109,1,not_seasonally_adjusted\n",
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] < 0.8


def test_leaving_a_reversed_claim_supported_loses_state_and_closure() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        path = workspace / "report_state.json"
        state = json.loads(path.read_text(encoding="utf-8"))
        state["claim_decisions"]["employment_increased"] = "retain_supported"
        path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.6
    assert result["task_success"] is False


def test_omitting_one_series_breaks_claim_state_and_closure() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        path = workspace / "report_state.json"
        state = json.loads(path.read_text(encoding="utf-8"))
        state["series_used"] = ["EMP_SA"]
        state["claim_decisions"]["average_hours_decreased"] = "retain_supported"
        path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] < 0.8
    assert result["failed_gates"] == []


def test_wrong_delta_breaks_revision_rows_without_zeroing_unrelated_work() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        path = workspace / "revisions.csv"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "EMP_SA,2026-06,108.0,102.0,-6.0", "EMP_SA,2026-06,108.0,102.0,6.0"
            ),
            encoding="utf-8",
        )
        result = _score(workspace)
    assert 0.0 < result["outcome_score"] < 0.8
    assert result["failed_gates"] == []


def test_source_mutation_is_a_redline() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        source = workspace / "old_claims.json"
        source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_input_integrity"]
