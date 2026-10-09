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


def test_plain_language_dispositions_and_path_buckets_are_valid() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        ledger = workspace / "path_coverage.csv"
        ledger.write_text(
            ledger.read_text(encoding="utf-8")
            .replace(",satisfied,", ",approved,")
            .replace(
                "src/payments/generated/client.py,platform,missing,platb",
                "src/payments/generated/client.py,platform,false,platb",
            )
            .replace(
                "scripts/release-payments.sh,release,missing,rela",
                "scripts/release-payments.sh,release,false,rela",
            )
            .replace(
                "infra/payment-job.json,sre,blocked,srec",
                "infra/payment-job.json,sre,false,srec",
            ),
            encoding="utf-8",
        )
        (workspace / "review_state.json").write_text(
            json.dumps(
                {
                    "head_sha": "e4b201",
                    "satisfied": [
                        "src/payments/core.py",
                        "docs/payments/runbook.md",
                        "config/secrets/payment.yaml",
                        "src/shared/logging.py",
                        ".github/workflows/payment.yml",
                    ],
                    "missing": [
                        "src/payments/generated/client.py",
                        "scripts/release-payments.sh",
                    ],
                    "blocked": ["infra/payment-job.json"],
                    "decision": "BLOCKED",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_current_approval_reason_uses_the_rest_of_its_business_row() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        ledger = workspace / "path_coverage.csv"
        ledger.write_text(
            ledger.read_text(encoding="utf-8").replace(
                "current_team_approval",
                "Current approval",
            ),
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_mixed_or_ambiguous_state_representation_does_not_pass() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        state = json.loads(
            (workspace / "review_state.json").read_text(encoding="utf-8")
        )
        state["satisfied"] = False
        state["missing"] = ["src/payments/generated/client.py"]
        state["blocked"] = ["infra/payment-job.json"]
        (workspace / "review_state.json").write_text(
            json.dumps(state, indent=2) + "\n", encoding="utf-8"
        )
        result = _score(workspace)
    assert result["outcome_score"] == 0.7
    assert result["task_success"] is False


def test_wrong_owner_loses_the_business_case_without_triggering_a_gate() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        ledger = workspace / "path_coverage.csv"
        ledger.write_text(
            ledger.read_text(encoding="utf-8").replace(
                "src/payments/generated/client.py,platform,",
                "src/payments/generated/client.py,payments,",
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
