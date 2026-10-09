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


def test_human_readable_page_ids_are_accepted() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        state_path = workspace / "vintage_state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["pages_consumed"] = ["page 3", "Page 2", "page1.json"]
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_page_count_scalar_loses_only_the_vintage_state_case() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        state_path = workspace / "vintage_state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["pages_consumed"] = 3
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.75
    assert result["task_success"] is False
    assert result["failed_gates"] == []


def test_omitting_a_country_year_breaks_panel_and_closure() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        panel = workspace / "indicator_panel.csv"
        panel.write_text(
            panel.read_text(encoding="utf-8").replace(
                "Cygnus,2025,GDPCON15,constant 2015 credits,540,\n", ""
            ),
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] < 0.8
    assert result["failed_gates"] == []


def test_source_mutation_is_a_redline() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        source = workspace / "request.md"
        source.write_text(
            source.read_text(encoding="utf-8") + "\nchanged\n",
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_input_integrity"]
