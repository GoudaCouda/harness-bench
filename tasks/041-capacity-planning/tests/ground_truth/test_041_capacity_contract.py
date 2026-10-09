from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
ORACLE_PATH = Path(__file__).with_name("oracle_impl.py")


def _load_oracle():
    spec = importlib.util.spec_from_file_location("oracle_041", ORACLE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ORACLE = _load_oracle()


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


def test_missing_incompatible_risk_does_not_erase_handoff(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    path = workspace / "risk_tradeoffs.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text(
        "\n".join(line for line in lines if "incompatib" not in line.casefold()) + "\n",
        encoding="utf-8",
    )

    result = ORACLE.score_workspace(workspace)
    checks = _checks(result)
    assert result["outcome_score"] == 0.79
    assert not checks["risk_tradeoffs"]["pass"]
    assert checks["planning_handoff"]["pass"]


def test_plan_total_mismatch_breaks_plan_and_handoff(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    path = workspace / "capacity_plan.json"
    text = path.read_text(encoding="utf-8").replace(
        '"total_hourly_cost_usd": 0.552', '"total_hourly_cost_usd": 0.652'
    )
    path.write_text(text, encoding="utf-8")

    result = ORACLE.score_workspace(workspace)
    checks = _checks(result)
    assert not checks["capacity_plan"]["pass"]
    assert not checks["planning_handoff"]["pass"]


def test_semantic_incompatible_rejection_is_accepted(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    path = workspace / "risk_tradeoffs.csv"
    text = path.read_text(encoding="utf-8").replace(
        "incompatible",
        "compatibility flag is false, so this option is excluded",
    )
    path.write_text(text, encoding="utf-8")
    assert _checks(ORACLE.score_workspace(workspace))["risk_tradeoffs"]["pass"]


def test_fixture_mutation_zeroes_score(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    (workspace / "traffic_history.csv").write_text("changed", encoding="utf-8")
    assert ORACLE.score_workspace(workspace)["outcome_score"] == 0.0
