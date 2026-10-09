from __future__ import annotations

import importlib.util
import json
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases


TASK = Path(__file__).resolve().parents[2]
REFERENCE = TASK / "tests" / "reference"


def _score(workspace: Path) -> dict[str, object]:
    spec = importlib.util.spec_from_file_location(
        "task_outcome_110", TASK / "tests" / "test_outcome.py"
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


def _workspace(
    *, reference: bool
) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory(prefix="hb110-contract-")
    workspace = Path(temporary.name) / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    if reference:
        shutil.copytree(REFERENCE, workspace, dirs_exist_ok=True)
    return temporary, workspace


def _run(workspace: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "bulletinctl.py", *arguments],
        cwd=workspace,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _artifact_bytes(workspace: Path) -> dict[str, bytes]:
    return {
        name: (workspace / name).read_bytes()
        for name in (
            "approved_bulletin.docx",
            "review_state.db",
            "verification_receipt.json",
        )
    }


def test_reference_scores_one_and_is_deterministic() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        first = _score(workspace)
        second = _score(workspace)
    assert first["outcome_score"] == 1.0
    assert second["outcome_score"] == 1.0
    assert first["checks"] == second["checks"]


def test_reference_semantic_input_builder_uses_supported_contract() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        spec = importlib.util.spec_from_file_location(
            "task_outcome_110_semantic", TASK / "tests" / "test_outcome.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        candidate = module.build_semantic_judge_input(workspace)
    assert candidate["artifact"] == "editorial_handoff.md"
    assert len(str(candidate["text"])) >= 400


def test_empty_workspace_scores_zero() -> None:
    with tempfile.TemporaryDirectory(prefix="hb110-empty-") as temporary:
        workspace = Path(temporary) / "workspace"
        workspace.mkdir()
        result = _score(workspace)
    assert result["outcome_score"] == 0.0


def test_untouched_seed_scores_zero() -> None:
    temporary, workspace = _workspace(reference=False)
    with temporary:
        result = _score(workspace)
    assert result["outcome_score"] == 0.0


def test_malformed_required_artifacts_score_zero() -> None:
    temporary, workspace = _workspace(reference=False)
    with temporary:
        for name in (
            "approved_bulletin.docx",
            "review_state.db",
            "adjudication_plan.json",
            "verification_receipt.json",
            "editorial_handoff.md",
        ):
            (workspace / name).write_bytes(b"malformed\n")
        result = _score(workspace)
    assert result["outcome_score"] == 0.0


def test_source_mutation_triggers_redline() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        path = workspace / "revision_manifest.json"
        path.write_text(path.read_text() + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["source_controller_and_publication_safety"]


def test_controller_mutation_triggers_redline() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        path = workspace / "bulletinctl.py"
        path.write_text(path.read_text() + "\n# changed\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["source_controller_and_publication_safety"]


def test_apply_and_verify_replay_are_byte_stable() -> None:
    temporary, workspace = _workspace(reference=False)
    with temporary:
        for name in ("adjudication_plan.json", "editorial_handoff.md"):
            shutil.copy2(REFERENCE / name, workspace / name)
        _run(workspace, "preview", "--plan", "adjudication_plan.json")
        _run(workspace, "apply", "--plan", "adjudication_plan.json")
        _run(workspace, "verify", "--plan", "adjudication_plan.json")
        _run(workspace, "verify", "--plan", "adjudication_plan.json")
        before = _artifact_bytes(workspace)
        completed = _run(
            workspace, "apply", "--plan", "adjudication_plan.json"
        )
        _run(workspace, "verify", "--plan", "adjudication_plan.json")
        after = _artifact_bytes(workspace)
        result = _score(workspace)
    assert json.loads(completed.stdout)["status"] == "idempotent"
    assert before == after
    assert result["outcome_score"] == 1.0


def test_alternate_valid_plan_serialization_scores_one() -> None:
    temporary, workspace = _workspace(reference=False)
    with temporary:
        plan = json.loads((REFERENCE / "adjudication_plan.json").read_text())
        plan["actions"].reverse()
        for action in plan["actions"]:
            action["evidence"].reverse()
        reordered = {
            "actions": plan["actions"],
            "approval_boundary": plan["approval_boundary"],
            "adjudication_order": plan["adjudication_order"],
            "source_document": plan["source_document"],
            "workflow_id": plan["workflow_id"],
        }
        (workspace / "adjudication_plan.json").write_text(
            json.dumps(reordered, separators=(",", ":")), encoding="utf-8"
        )
        shutil.copy2(REFERENCE / "editorial_handoff.md", workspace / "editorial_handoff.md")
        _run(workspace, "preview", "--plan", "adjudication_plan.json")
        _run(workspace, "apply", "--plan", "adjudication_plan.json")
        _run(workspace, "verify", "--plan", "adjudication_plan.json")
        _run(workspace, "verify", "--plan", "adjudication_plan.json")
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_adjacent_error_older_signed_event_cannot_pass() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        path = workspace / "adjudication_plan.json"
        plan = json.loads(path.read_text())
        action = next(row for row in plan["actions"] if row["change_id"] == "CH-01")
        action["selected_event_id"] = "EV-107"
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] < 0.8
    assert "authoritative_revision_and_dependency_state" in result["failed_core_cases"]


def test_adjacent_error_child_of_rejected_parent_cannot_pass() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        path = workspace / "adjudication_plan.json"
        plan = json.loads(path.read_text())
        action = next(row for row in plan["actions"] if row["change_id"] == "CH-04")
        action["disposition"] = "reject"
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] < 0.8
    assert "authoritative_revision_and_dependency_state" in result["failed_core_cases"]


def test_invalid_preview_returns_feedback_without_mutation() -> None:
    temporary, workspace = _workspace(reference=False)
    with temporary:
        plan = json.loads((REFERENCE / "adjudication_plan.json").read_text())
        action = next(row for row in plan["actions"] if row["change_id"] == "CH-07")
        action["disposition"] = "accept"
        (workspace / "adjudication_plan.json").write_text(
            json.dumps(plan, indent=2) + "\n", encoding="utf-8"
        )
        before = (workspace / "review_state.db").read_bytes()
        completed = _run(
            workspace,
            "preview",
            "--plan",
            "adjudication_plan.json",
            check=False,
        )
        after = (workspace / "review_state.db").read_bytes()
        output_exists = (workspace / "approved_bulletin.docx").exists()
        assert completed.returncode == 2
        assert "CH-07" in completed.stdout
        assert before == after
        assert not output_exists


def test_stale_receipt_loses_only_closure_block() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        path = workspace / "verification_receipt.json"
        receipt = json.loads(path.read_text())
        receipt["source_bundle_sha256"] = "0" * 64
        path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.92
    assert result["failed_core_cases"] == []


def test_duplicate_recovery_transaction_is_rejected_by_oracle() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        connection = sqlite3.connect(workspace / "review_state.db")
        row = connection.execute(
            "SELECT * FROM transactions WHERE transaction_id='TX-05'"
        ).fetchone()
        duplicate = list(row)
        duplicate[0] = "TX-06"
        duplicate[1] = "f" * 64
        connection.execute(
            "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            duplicate,
        )
        connection.commit()
        connection.close()
        result = _score(workspace)
    assert result["outcome_score"] < 0.8
    assert "transaction_recovery_and_idempotence" in result["failed_core_cases"]

def test_symlinked_required_artifact_triggers_redline() -> None:
    temporary, workspace = _workspace(reference=True)
    with temporary:
        path = workspace / "editorial_handoff.md"
        path.unlink()
        path.symlink_to(REFERENCE / "editorial_handoff.md")
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == [
        "source_controller_and_publication_safety"
    ]
