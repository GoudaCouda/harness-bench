from __future__ import annotations

import csv
import importlib.util
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


def _workspace() -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory(prefix=f"{TASK.name}-")
    workspace = Path(temporary.name) / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    shutil.copytree(TASK / "tests" / "reference", workspace, dirs_exist_ok=True)
    return temporary, workspace


def test_reference_scores_full_credit_deterministically() -> None:
    temporary, workspace = _workspace()
    with temporary:
        first = _score(workspace)
        second = _score(workspace)
    assert first["outcome_score"] == 1.0
    assert second["checks"] == first["checks"]


def test_omitting_one_effective_risk_loses_the_main_business_case() -> None:
    temporary, workspace = _workspace()
    with temporary:
        path = workspace / "risk_clauses.csv"
        rows = list(csv.DictReader(path.open(encoding="utf-8")))
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(row for row in rows if row["clause_id"] != "C-06")
        result = _score(workspace)
    assert result["outcome_score"] < 0.8
    assert "effective_risk_register" in result["failed_core_cases"]


def test_superseded_master_term_is_not_an_extra_open_risk() -> None:
    temporary, workspace = _workspace()
    with temporary:
        path = workspace / "risk_clauses.csv"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(
                "contract.md,C-03,Data may be stored anywhere,High,Restrict regions,Privacy\n"
            )
        result = _score(workspace)
    assert result["outcome_score"] < 0.8
    assert "effective_risk_register" in result["failed_core_cases"]


def test_equivalent_owner_and_action_wording_is_accepted() -> None:
    temporary, workspace = _workspace()
    with temporary:
        path = workspace / "risk_clauses.csv"
        text = path.read_text(encoding="utf-8").replace(
            "Increase coverage to USD 2 million or obtain a scoped approved exception,Risk",
            "Require 2 million USD coverage or a deal-specific approved exception,Finance and Risk",
        )
        path.write_text(text, encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_deal_team_owner_with_concrete_actions_is_accepted() -> None:
    temporary, workspace = _workspace()
    with temporary:
        path = workspace / "risk_clauses.csv"
        rows = list(csv.DictReader(path.open(encoding="utf-8")))
        for row in rows:
            row["owner"] = "Deal Team"
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_owner_does_not_rescue_a_non_actionable_disposition() -> None:
    temporary, workspace = _workspace()
    with temporary:
        path = workspace / "risk_clauses.csv"
        rows = list(csv.DictReader(path.open(encoding="utf-8")))
        rows[0]["owner"] = "Deal Team"
        rows[0]["recommended_action"] = "Review later"
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        result = _score(workspace)
    assert result["outcome_score"] < 1.0


def test_hyphenated_time_periods_are_semantically_equivalent() -> None:
    temporary, workspace = _workspace()
    with temporary:
        register = workspace / "risk_clauses.csv"
        register.write_text(
            register.read_text(encoding="utf-8")
            .replace("60 calendar days", "60-calendar-days")
            .replace("30 calendar days", "30-calendar-days")
            .replace("15 calendar days", "15-calendar-days"),
            encoding="utf-8",
        )
        summary = workspace / "contract_summary.md"
        summary.write_text(
            summary.read_text(encoding="utf-8")
            .replace("24 months", "24-month")
            .replace("48 hours", "48-hour")
            .replace("15 calendar days", "15-calendar-days"),
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_source_mutation_is_a_redline() -> None:
    temporary, workspace = _workspace()
    with temporary:
        source = workspace / "order_form.md"
        source.write_text(
            source.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8"
        )
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_input_integrity"]
