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


def test_equivalent_valid_and_quarantined_statuses_are_accepted() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        records = workspace / "qc_records.csv"
        records.write_text(
            records.read_text(encoding="utf-8")
            .replace(",included,", ",valid,")
            .replace(",excluded,", ",quarantined,"),
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_excluded_flagged_row_may_retain_its_converted_source_value() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        records = workspace / "qc_records.csv"
        records.write_text(
            records.read_text(encoding="utf-8").replace(
                "ST-B,2026-01-01,,excluded,qflag_x",
                "ST-B,2026-01-01,12.0,excluded,QFLAG=X",
            ),
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_excluded_flagged_row_cannot_invent_a_different_value() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        records = workspace / "qc_records.csv"
        records.write_text(
            records.read_text(encoding="utf-8").replace(
                "ST-B,2026-01-01,,excluded,qflag_x",
                "ST-B,2026-01-01,99.0,excluded,QFLAG=X",
            ),
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] < 1.0


def test_fraction_and_percentage_coverage_wording_is_accepted() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        note = workspace / "qc_note.md"
        note.write_text(
            note.read_text(encoding="utf-8")
            .replace("6/7 usable days", "6/7 usable days (85.7%)")
            .replace("ST-B has 4/7", "ST-B has 4/7 (57.1%)")
            .replace("ST-D 2/7", "ST-D 2/7 (28.6%)"),
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_overall_coverage_scalar_loses_state_and_cross_artifact_closure() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        state_path = workspace / "coverage.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["coverage"] = 0.5
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.6
    assert result["task_success"] is False
    assert result["failed_gates"] == []


def test_including_a_sentinel_breaks_qc_and_cross_artifact_closure() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        records = workspace / "qc_records.csv"
        records.write_text(
            records.read_text(encoding="utf-8").replace(
                "ST-A,2026-01-03,,excluded,sentinel",
                "ST-A,2026-01-03,-999.9,valid,sentinel",
            ),
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] < 0.8
    assert result["failed_gates"] == []


def test_source_mutation_is_a_redline() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        source = workspace / "policy.md"
        source.write_text(
            source.read_text(encoding="utf-8") + "\nchanged\n",
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_input_integrity"]
