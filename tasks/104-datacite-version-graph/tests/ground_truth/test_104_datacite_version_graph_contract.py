from __future__ import annotations

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


def _evaluator_module():
    spec = importlib.util.spec_from_file_location(
        "task_outcome_boundary_test", TASK / "tests" / "test_outcome.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load task evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_published_none_boundary_is_accepted_for_removal_actions() -> None:
    evaluator = _evaluator_module()
    cases = (
        (
            "remove_duplicate",
            "relations.json#R5",
            "10.data/cohort|HasVersion|10.data/cohort.v3",
        ),
        (
            "remove_self_edge",
            "relations.json#R9",
            "10.data/cohort.v3|IsNewVersionOf|10.data/cohort.v3",
        ),
        (
            "remove_draft_edge",
            "relations.json#R10",
            "10.data/cohort.v3-draft|IsVersionOf|10.data/cohort",
        ),
        (
            "remove_duplicate_citation",
            "citations.json#C1-DUP",
            "10.paper/alpha|Cites|10.data/cohort.v2",
        ),
    )
    for action, source_ref, before_value in cases:
        assert evaluator._change_values_ok(
            {
                "action": action,
                "source_ref": source_ref,
                "before_value": before_value,
                "after_value": "none",
            }
        )
