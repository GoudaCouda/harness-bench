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


def test_cardinality_aliases_are_accepted_per_relation() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        path = workspace / "close" / "join_audit.json"
        state = json.loads(path.read_text(encoding="utf-8"))
        state["cardinality"] = {
            "orders-customers": "many-to-one",
            "orders/rates": "M:1",
        }
        path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_rejected_rows_may_record_zero_revenue_contribution() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        path = workspace / "close" / "order_join.csv"
        text = path.read_text(encoding="utf-8")
        text = text.replace(
            "o3,rejected,,,null_customer_key", "o3,rejected,,0,null_customer_key"
        )
        text = text.replace(
            "o4,rejected,,,unmatched_customer", "o4,rejected,,0,unmatched_customer"
        )
        path.write_text(text, encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_rejected_rows_cannot_contribute_nonzero_revenue() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        path = workspace / "close" / "order_join.csv"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "o3,rejected,,,null_customer_key", "o3,rejected,,50,null_customer_key"
            ),
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] < 1.0


def test_undifferentiated_cardinality_loses_the_audit_block() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        path = workspace / "close" / "join_audit.json"
        state = json.loads(path.read_text(encoding="utf-8"))
        state["cardinality"] = "m:1 enforced"
        path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.7
    assert result["task_success"] is False


def test_matching_ambiguous_customer_breaks_rows_and_revenue_closure() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        path = workspace / "close" / "order_join.csv"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "o5,rejected,,,ambiguous_customer",
                "o5,matched,A,60,selected_first_duplicate",
            ),
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] < 0.8
    assert result["failed_gates"] == []


def test_refund_sign_error_breaks_rows_and_revenue_closure() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        path = workspace / "close" / "order_join.csv"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "o12,matched,D,-10.0,", "o12,matched,D,10.0,"
            ),
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] < 0.8


def test_source_mutation_is_a_redline() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        source = workspace / "policy.md"
        source.write_text(
            source.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8"
        )
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_input_integrity"]
