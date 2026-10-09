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


def test_equivalent_revalidation_actions_and_pending_label_are_accepted() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        ledger = workspace / "queue_gates.csv"
        ledger.write_text(
            ledger.read_text(encoding="utf-8")
            .replace("wait_for_current_scan", "run_current_scan")
            .replace("request_current_sha_reapproval", "request_approval"),
            encoding="utf-8",
        )
        state_path = workspace / "queue_state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["queue_state"] = "pending"
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        transition = workspace / "transition.md"
        transition.write_text(
            "# Queue handoff\n\nThe conflict-resolution commit changed the SHA from "
            "`aaa111` to `bbb222`, so the old approval is stale and fresh approval "
            "is required. Both builds passed and release approval is current. Security "
            "remains pending; license failed on the GPL dependency and needs dependency "
            "remediation plus rerun. The queue is pending until security, license, and "
            "owner approval clear. Verification reconciled all gates. The PR has not "
            "been merged.\n",
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_pending_owner_gate_with_explicit_rerequest_invalidates_old_approval() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        ledger = workspace / "queue_gates.csv"
        ledger.write_text(
            ledger.read_text(encoding="utf-8").replace(
                "owner_approval,bbb222,stale,request_current_sha_reapproval,current_reviews.json:owna",
                "owner_approval,bbb222,pending,re-request owner approval,current_reviews.json:owna",
            ),
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_owner_gate_cannot_carry_forward_a_pass() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        ledger = workspace / "queue_gates.csv"
        ledger.write_text(
            ledger.read_text(encoding="utf-8").replace(
                "owner_approval,bbb222,stale,request_current_sha_reapproval,current_reviews.json:owna",
                "owner_approval,bbb222,pass,none,round1.json",
            ),
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] < 0.8


def test_human_readable_gate_labels_are_accepted() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        ledger = workspace / "queue_gates.csv"
        ledger.write_text(
            ledger.read_text(encoding="utf-8")
            .replace("build_linux,", "Linux Build,")
            .replace("build_windows,", "Windows Build,")
            .replace("security,", "Security,")
            .replace("license,", "License Scan,")
            .replace("owner_approval,", "Owner Approval,"),
            encoding="utf-8",
        )
        state_path = workspace / "queue_state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["pending_gates"] = ["Security", "License Scan", "Owner Approval"]
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_case_variants_cannot_hide_a_duplicate_or_missing_gate() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        ledger = workspace / "queue_gates.csv"
        ledger.write_text(
            ledger.read_text(encoding="utf-8").replace(
                "owner_approval,bbb222,stale,request_current_sha_reapproval,current_reviews.json:owna",
                "Linux Build,bbb222,pass,none,current_checks.json:run-201",
            ),
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] < 0.8
    assert result["failed_gates"] == []


def test_carrying_forward_old_security_result_loses_core_credit_not_gate() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        ledger = workspace / "queue_gates.csv"
        ledger.write_text(
            ledger.read_text(encoding="utf-8").replace(
                "security,bbb222,pending,wait_for_current_scan,current_checks.json:run-203",
                "security,bbb222,pass,none,round1.json",
            ),
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] < 0.8
    assert result["failed_gates"] == []
