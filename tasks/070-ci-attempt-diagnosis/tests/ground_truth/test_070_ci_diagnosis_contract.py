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


def test_plain_operator_classifications_and_actions_are_accepted() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        ledger = workspace / "job_ledger.csv"
        text = ledger.read_text(encoding="utf-8")
        replacements = {
            "unit,valid_success,preserve,1,pass,attempt1.json:unit":
                "unit,success,keep,1,success,attempt1.json",
            "windows,recoverable_runner_failure,rerun_once,2,pass,retry_update.json:windows":
                "windows,runner loss,retry,2,passed,retry_update.json",
            "integration,code_failure,patch_then_run,2,pass,patch_evidence.json:integration":
                "integration,assertion failure,fix then run,2,pass,patch_evidence.json",
            "package,stale_sha_artifact,run_current_sha,2,pass,package_update.json:sha256:new91":
                "package,stale artifact,replace for current SHA,2,pass,package_update.json",
        }
        for source, replacement in replacements.items():
            text = text.replace(source, replacement)
        ledger.write_text(text, encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_undifferentiated_retry_count_loses_only_run_state() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        state_path = workspace / "run_state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["retry_budget_used"] = 2
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.85
    assert result["task_success"] is False


def test_blindly_retrying_the_code_failure_loses_recovery_plan() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        ledger = workspace / "job_ledger.csv"
        ledger.write_text(
            ledger.read_text(encoding="utf-8").replace(
                "integration,code_failure,patch_then_run,2,pass,patch_evidence.json:integration",
                "integration,code_failure,retry,2,pass,patch_evidence.json:integration",
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
