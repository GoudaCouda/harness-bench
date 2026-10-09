from __future__ import annotations

import json
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import yaml


ROOT = Path(__file__).resolve().parents[1]
MAINTENANCE = ROOT / "tools" / "task_maintenance"
if str(MAINTENANCE) not in sys.path:
    sys.path.insert(0, str(MAINTENANCE))

from common import load_oracle, outcome_case_definition  # noqa: E402
from harnessbench.grading.outcome_cases import score_workspace_from_cases  # noqa: E402
from validate_oracle_quality import make_workspace  # noqa: E402


TASK_ID = "013-batch-quote-contract"


@contextmanager
def _reference_workspace() -> Iterator[tuple[Path, Path, dict]]:
    task = ROOT / "tasks" / TASK_ID
    metadata = yaml.safe_load((task / "task.yaml").read_text(encoding="utf-8"))
    workspace, cleanup_roots = make_workspace(task, metadata, "reference")
    try:
        yield workspace, task, metadata
    finally:
        for cleanup_root in cleanup_roots:
            shutil.rmtree(cleanup_root, ignore_errors=True)


def _score(workspace: Path, task: Path, metadata: dict) -> dict:
    _, manifest = outcome_case_definition(task, metadata)
    module = load_oracle(task / metadata["outcome_test"], metadata["task_id"])
    return score_workspace_from_cases(
        workspace,
        manifest=manifest,
        evaluate_cases=module.evaluate_cases,
        task_id=metadata["task_id"],
    )


def test_013_reference_solution_passes_every_case() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        result = _score(workspace, task, metadata)

    assert result["outcome_score"] == 1.0
    assert result["task_success"] is True
    assert result["failed_core_cases"] == []


def test_013_detects_discount_order_regression() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        source_path = workspace / "repo/src/quote_service/batch.py"
        source = source_path.read_text(encoding="utf-8")
        source_path.write_text(
            source.replace(
                'coupon_discount = after_term * coupon["discount_bps"] // 10000',
                'coupon_discount = subtotal * coupon["discount_bps"] // 10000',
            ),
            encoding="utf-8",
        )
        result = _score(workspace, task, metadata)

    assert result["outcome_score"] < 1.0
    assert "pricing_behavior" in result["failed_core_cases"]


def test_013_detects_duplicate_request_regression() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        source_path = workspace / "repo/src/quote_service/batch.py"
        source = source_path.read_text(encoding="utf-8")
        source_path.write_text(
            source.replace(
                "if counts.get(request_id, 0) > 1:",
                "if counts.get(request_id, 0) > 2:",
            ),
            encoding="utf-8",
        )
        result = _score(workspace, task, metadata)

    assert result["outcome_score"] < 1.0
    assert "validation_and_partial_success" in result["failed_core_cases"]


def test_013_detects_openapi_batch_bound_regression() -> None:
    with _reference_workspace() as (workspace, task, metadata):
        contract_path = workspace / "repo/api/openapi.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        requests = contract["paths"]["/quotes/batch"]["post"]["requestBody"][
            "content"
        ]["application/json"]["schema"]["properties"]["requests"]
        requests["maxItems"] = 500
        contract_path.write_text(
            json.dumps(contract, indent=2) + "\n",
            encoding="utf-8",
        )
        result = _score(workspace, task, metadata)

    assert result["outcome_score"] < 1.0
    assert "api_contract_compatibility" in result["failed_core_cases"]
