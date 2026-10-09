from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]


def _load(relative: str, name: str):
    path = TASK / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ORACLE = _load("tests/ground_truth/oracle_impl.py", "oracle_083")
OUTCOME = _load("tests/test_outcome.py", "outcome_083")


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    for source in (TASK / "tests" / "reference").iterdir():
        shutil.copy2(source, workspace / source.name)
    return workspace


def _checks(result: dict) -> dict[str, dict]:
    return {check["id"]: check for check in result["checks"]}


def test_reference_scores_one(tmp_path: Path) -> None:
    result = ORACLE.score_workspace(_workspace(tmp_path))
    assert result["outcome_score"] == 1.0


def test_logical_variable_and_plain_status_are_valid(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    path = workspace / "panel.csv"
    text = path.read_text(encoding="utf-8")
    text = text.replace(",P001,", ",resident_population_estimate,")
    text = text.replace(",P101,", ",resident_population_estimate,")
    text = text.replace(",observed", ",valid").replace(",suppressed", ",not published")
    path.write_text(text, encoding="utf-8")
    result = ORACLE.score_workspace(workspace)
    checks = _checks(result)
    assert checks["observed_panel"]["pass"]
    assert checks["incomplete_evidence"]["pass"]


def test_one_wrong_observed_value_loses_panel_but_not_independent_analysis(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    path = workspace / "panel.csv"
    path.write_text(
        path.read_text(encoding="utf-8").replace("P101,126,12", "P101,162,12"),
        encoding="utf-8",
    )
    checks = _checks(ORACLE.score_workspace(workspace))
    assert not checks["observed_panel"]["pass"]
    assert checks["change_analysis"]["pass"]
    assert not checks["cross_artifact_closure"]["pass"]


def test_suppressed_value_cannot_be_zero_filled(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    path = workspace / "panel.csv"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "06,007,2025,P101,,,suppressed",
            "06,007,2025,P101,0,0,observed",
        ),
        encoding="utf-8",
    )
    result = ORACLE.score_workspace(workspace)
    checks = _checks(result)
    assert not checks["incomplete_evidence"]["pass"]
    assert result["outcome_score"] <= 0.75


def test_out_of_scope_same_name_row_loses_integrity(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with (workspace / "panel.csv").open("a", encoding="utf-8") as handle:
        handle.write("41,099,2025,P101,1040,34,observed\n")
    checks = _checks(ORACLE.score_workspace(workspace))
    assert checks["observed_panel"]["pass"]
    assert not checks["panel_integrity"]["pass"]


def test_analysis_must_close_against_submitted_panel(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    path = workspace / "analysis.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["observed_rows"] = 8
    value["incomplete_counties"] = []
    path.write_text(json.dumps(value), encoding="utf-8")
    checks = _checks(ORACLE.score_workspace(workspace))
    assert not checks["change_analysis"]["pass"]
    assert not checks["incomplete_evidence"]["pass"]
    assert not checks["cross_artifact_closure"]["pass"]


def test_fixture_mutation_fails_safety_gate(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    (workspace / "variables.json").write_text("{}", encoding="utf-8")
    assert not OUTCOME.evaluate_cases(workspace)["safety_and_input_integrity"]["pass"]
