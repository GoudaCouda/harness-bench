from __future__ import annotations

import ast
import hashlib
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


def _module():
    spec = importlib.util.spec_from_file_location("task197_outcome", TASK / "tests/test_outcome.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _score(workspace: Path) -> dict[str, object]:
    return score_workspace_from_cases(
        workspace,
        manifest=yaml.safe_load((TASK / "tests/cases.yaml").read_text(encoding="utf-8")),
        evaluate_cases=_module().evaluate_cases,
        task_id=TASK.name,
    )


def _workspace(reference: bool) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory(prefix="hb197-")
    workspace = Path(temporary.name) / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    if reference:
        shutil.copytree(TASK / "tests/reference", workspace, dirs_exist_ok=True)
    return temporary, workspace


def _run(workspace: Path, command: str, plan: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "continuancectl.py", command, plan], cwd=workspace,
        check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_oracle_scores_empty_pristine_malformed_reference_as_0001() -> None:
    with tempfile.TemporaryDirectory(prefix="hb197-empty-") as empty:
        assert _score(Path(empty))["outcome_score"] == 0.0
    temporary, workspace = _workspace(False)
    with temporary:
        assert _score(workspace)["outcome_score"] == 0.0
        (workspace / "recovery_plan.json").write_bytes(b"\xff{")
        (workspace / "state/continuance.db").write_bytes(b"not sqlite")
        (workspace / "continuance_handoff.md").write_bytes(b"\xff")
        assert _score(workspace)["outcome_score"] == 0.0
    temporary, workspace = _workspace(True)
    with temporary:
        first, second = _score(workspace), _score(workspace)
    assert first["outcome_score"] == second["outcome_score"] == 1.0
    assert first["checks"] == second["checks"]


def test_source_or_controller_mutation_triggers_gate() -> None:
    for relative in (
        "policy/continuance_policy.json", "policy/source_manifest.json",
        "evidence/eligibility_events.jsonl", "evidence/delivery_receipts.jsonl",
        "state/stale_checkpoint.json", "continuancectl.py",
    ):
        temporary, workspace = _workspace(True)
        with temporary:
            path = workspace / relative
            path.write_bytes(path.read_bytes() + b"\n")
            result = _score(workspace)
        assert result["outcome_score"] == 0.0
        assert result["failed_gates"] == ["source_and_external_action_gate"]


def test_external_action_flag_or_affirmative_claim_triggers_gate() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        plan_path = workspace / "recovery_plan.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["external_notices_sent"] = True
        plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["source_and_external_action_gate"]

    temporary, workspace = _workspace(True)
    with temporary:
        handoff = workspace / "continuance_handoff.md"
        handoff.write_text(handoff.read_text(encoding="utf-8") + "\nWe sent the corrected notices.\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["source_and_external_action_gate"]


def test_preview_rejects_neighbor_beneficiary_receipt_address_deadline_and_identity_errors() -> None:
    mutations = (
        ("COV-7201", "beneficiary_keys", ["P-7201-E"]),
        ("COV-7202", "delivery_evidence", "evidence/delivery_receipts.jsonl#receipt:RCPT-7202-T"),
        ("COV-7203", "address_version", 1),
        ("COV-7206", "disposition", "prepare_initial_notice"),
        ("COV-7207", "deadline_state", "open"),
    )
    for case_id, field, value in mutations:
        temporary, workspace = _workspace(False)
        with temporary:
            plan = json.loads((TASK / "tests/reference/recovery_plan.json").read_text(encoding="utf-8"))
            next(row for row in plan["case_decisions"] if row["case_id"] == case_id)[field] = value
            (workspace / "recovery_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            before = (workspace / "state/continuance.db").read_bytes()
            completed = _run(workspace, "preview", "recovery_plan.json", check=False)
            after = (workspace / "state/continuance.db").read_bytes()
            diagnostics = json.loads((workspace / ".continuance_preview.json").read_text(encoding="utf-8"))["discrepancies"]
        assert completed.returncode == 2
        assert before == after
        assert any(row.get("id") == case_id and row.get("field") == field for row in diagnostics)
        assert all("expected" not in row and "wanted" not in row and "actual" not in row for row in diagnostics)


def test_near_correct_plan_loses_owning_core() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "recovery_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        next(row for row in plan["case_decisions"] if row["case_id"] == "COV-7202")["disposition"] = "hold_delivery_investigation"
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert "receipt_deadline_and_post_notice_recovery" in result["failed_core_cases"]
    assert result["outcome_score"] < 0.8


def test_sqlite_case_attempt_queue_receipt_run_and_journal_corruption_cannot_pass() -> None:
    statements = (
        "UPDATE cases SET case_state='retry' WHERE case_id='COV-7202'",
        "UPDATE delivery_attempts SET delivered_at=NULL WHERE attempt_id='ATT-7205-1'",
        "UPDATE recovery_queue SET executed=1 WHERE case_id='COV-7203'",
        "DELETE FROM decision_receipts WHERE case_id='COV-7206'",
        "UPDATE recovery_runs SET status='interrupted' WHERE recovery_id='CONT-REC-2026-08-14'",
        "UPDATE recovery_journal SET restored=0 WHERE journal_id='J-OLD-CASE-7203'",
    )
    for statement in statements:
        temporary, workspace = _workspace(True)
        with temporary:
            with sqlite3.connect(workspace / "state/continuance.db") as connection:
                connection.execute(statement)
                connection.commit()
            result = _score(workspace)
        assert "journal_and_atomic_sqlite_recovery" in result["failed_core_cases"]
        assert result["outcome_score"] < 0.8


def test_complete_guarded_workflow_recovers_pristine_workspace() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        for name in ("recovery_plan.json", "equivalent_recovery_plan.json", "conflict_probe_plan.json", "continuance_handoff.md"):
            shutil.copy2(TASK / "tests/reference" / name, workspace / name)
        for command in ("preview", "apply", "verify", "stage"):
            assert _run(workspace, command, "recovery_plan.json").returncode == 0
        assert _run(workspace, "replay", "equivalent_recovery_plan.json").returncode == 0
        tracked = {"database": workspace / "state/continuance.db", "bundle": workspace / "staging/notice_review_queue.json", "manifest": workspace / "staging/queue_manifest.json", "receipt": workspace / "state/staging_receipt.json"}
        before = {key: _sha(path) for key, path in tracked.items()}
        completed = _run(workspace, "apply", "conflict_probe_plan.json", check=False)
        after = {key: _sha(path) for key, path in tracked.items()}
        (workspace / "conflict_probe.json").write_text(json.dumps({"schema_version": 1, "command": "python3 continuancectl.py apply conflict_probe_plan.json", "exit_code": completed.returncode, "changed_field": "case_decisions[COV-7204].next_local_action", "before_sha256": before, "after_sha256": after}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_equivalent_semantic_replay_is_byte_stable() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        tracked = [workspace / "state/continuance.db", workspace / "staging/notice_review_queue.json", workspace / "staging/queue_manifest.json", workspace / "state/staging_receipt.json"]
        before = [path.read_bytes() for path in tracked]
        completed = _run(workspace, "replay", "equivalent_recovery_plan.json")
        after = [path.read_bytes() for path in tracked]
    assert completed.returncode == 0
    assert before == after


def test_conflict_and_stale_checkpoint_reject_without_write() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        tracked = [workspace / "state/continuance.db", workspace / "staging/notice_review_queue.json", workspace / "staging/queue_manifest.json", workspace / "state/staging_receipt.json"]
        before = [path.read_bytes() for path in tracked]
        completed = _run(workspace, "apply", "conflict_probe_plan.json", check=False)
        after = [path.read_bytes() for path in tracked]
    assert completed.returncode == 2
    assert before == after

    temporary, workspace = _workspace(False)
    with temporary:
        plan = json.loads((TASK / "tests/reference/recovery_plan.json").read_text(encoding="utf-8"))
        plan["source_checkpoint"] = "0" * 64
        (workspace / "recovery_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        before = _sha(workspace / "state/continuance.db")
        completed = _run(workspace, "apply", "recovery_plan.json", check=False)
        after = _sha(workspace / "state/continuance.db")
    assert completed.returncode == 2
    assert before == after


def test_public_preview_changes_for_valid_seed_mutation() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        events_path = workspace / "evidence/eligibility_events.jsonl"
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
        next(row for row in events if row["event_id"] == "EV-7201-BEN3")["beneficiary_keys"] = ["P-7201-E"]
        events_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in events), encoding="utf-8")
        manifest_path = workspace / "policy/source_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"]["evidence/eligibility_events.jsonl"] = _sha(events_path)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        shutil.copy2(TASK / "tests/reference/recovery_plan.json", workspace / "recovery_plan.json")
        completed = _run(workspace, "preview", "recovery_plan.json", check=False)
        diagnostics = json.loads((workspace / ".continuance_preview.json").read_text(encoding="utf-8"))["discrepancies"]
    assert completed.returncode == 2
    assert any(row.get("id") == "COV-7201" and row.get("field") in {"beneficiary_keys", "disposition", "notice_version", "next_local_action"} for row in diagnostics)


def test_public_controller_has_no_complete_answer_export() -> None:
    source = (TASK / "workspace/continuancectl.py").read_text(encoding="utf-8")
    names = {node.name for node in ast.walk(ast.parse(source)) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    forbidden = {"derive", "expected_plan", "target_plan", "reference_plan", "build_plan", "expected_verification"}
    assert not names & forbidden
    assert "tests/reference" not in source and "ground_truth" not in source
    completed = subprocess.run(
        ["python3", "-B", "-c", "import continuancectl; forbidden={'derive','expected_plan','target_plan','reference_plan','build_plan','expected_verification'}; assert not forbidden & set(dir(continuancectl))"],
        cwd=TASK / "workspace", check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    assert completed.returncode == 0, completed.stdout


def test_regular_helpers_and_cache_are_fair_but_symlink_fails_gate() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        (workspace / "inspect_cases.py").write_text("import sqlite3\n", encoding="utf-8")
        (workspace / "query_cases.sql").write_text("SELECT * FROM cases;\n", encoding="utf-8")
        subprocess.run(["python3", "-B", "-c", "import continuancectl"], cwd=workspace, check=True)
        result = _score(workspace)
    assert result["outcome_score"] == 1.0
    temporary, workspace = _workspace(True)
    with temporary:
        (workspace / "unsafe-link").symlink_to(workspace / "continuancectl.py")
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["source_and_external_action_gate"]


def test_evaluator_weights_semantic_builder_and_independence_contract() -> None:
    source = (TASK / "tests/test_outcome.py").read_text(encoding="utf-8")
    assert "import continuancectl" not in source and "subprocess" not in source
    cases = yaml.safe_load((TASK / "tests/cases.yaml").read_text(encoding="utf-8"))["cases"]
    assert sum(row["weight"] for row in cases if row.get("core")) == 0.8
    assert sum(row["weight"] for row in cases) == 1.0
    assert [row["id"] for row in cases if row.get("gate")] == ["source_and_external_action_gate"]
    metadata = yaml.safe_load((TASK / "task.yaml").read_text(encoding="utf-8"))
    assert metadata["semantic_judge"]["case_map"] == {"handoff_semantics": "continuance_recovery_handoff"}
    assert metadata["semantic_judge"]["max_fallback_weight"] == 0.08
    temporary, workspace = _workspace(True)
    with temporary:
        semantic_input = _module().build_semantic_judge_input(workspace)
    assert semantic_input["judge_eligible"] is True
    assert semantic_input["artifact"] == "continuance_handoff.md"
