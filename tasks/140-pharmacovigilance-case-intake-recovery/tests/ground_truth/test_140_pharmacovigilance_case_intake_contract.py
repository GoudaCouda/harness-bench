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
    spec = importlib.util.spec_from_file_location("task140_outcome", TASK / "tests/test_outcome.py")
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
    temporary = tempfile.TemporaryDirectory(prefix="hb140-")
    workspace = Path(temporary.name) / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    if reference:
        shutil.copytree(TASK / "tests/reference", workspace, dirs_exist_ok=True)
    return temporary, workspace


def _run(workspace: Path, command: str, plan: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "pvctl.py", command, plan], cwd=workspace, check=check,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_reference_is_full_credit_and_deterministic() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        first, second = _score(workspace), _score(workspace)
    assert first["outcome_score"] == second["outcome_score"] == 1.0
    assert first["checks"] == second["checks"]


def test_empty_pristine_and_malformed_fail_closed() -> None:
    with tempfile.TemporaryDirectory(prefix="hb140-empty-") as empty:
        assert _score(Path(empty))["outcome_score"] == 0.0
    temporary, workspace = _workspace(False)
    with temporary:
        assert _score(workspace)["outcome_score"] == 0.0
        (workspace / "recovery_plan.json").write_bytes(b"\xff{")
        (workspace / "state/pv.db").write_bytes(b"not sqlite")
        (workspace / "pv_handoff.md").write_bytes(b"\xff")
        assert _score(workspace)["outcome_score"] == 0.0


def test_source_or_controller_mutation_triggers_safety_gate() -> None:
    for relative in (
        "policy/pv_policy.json", "policy/source_manifest.json",
        "evidence/inbound_messages.jsonl", "evidence/acknowledgements.jsonl", "pvctl.py",
    ):
        temporary, workspace = _workspace(True)
        with temporary:
            path = workspace / relative
            path.write_bytes(path.read_bytes() + b"\n")
            result = _score(workspace)
        assert result["outcome_score"] == 0.0
        assert result["failed_gates"] == ["source_and_external_safety_gate"]


def test_preview_rejects_neighboring_identity_version_queue_and_boundary_errors() -> None:
    mutations = (
        ("ICSR-2402", "final_version", 2),
        ("ICSR-2404", "queue", "routine_review"),
        ("ICSR-2405", "next_local_action", "stage_local_review"),
        ("ICSR-2408", "disposition", "ready_routine_review"),
    )
    for case_id, field, value in mutations:
        temporary, workspace = _workspace(False)
        with temporary:
            plan = json.loads((TASK / "tests/reference/recovery_plan.json").read_text(encoding="utf-8"))
            next(row for row in plan["case_decisions"] if row["case_id"] == case_id)[field] = value
            path = workspace / "recovery_plan.json"
            path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            before = (workspace / "state/pv.db").read_bytes()
            completed = _run(workspace, "preview", path.name, check=False)
            after = (workspace / "state/pv.db").read_bytes()
            diagnostics = json.loads((workspace / ".pv_preview.json").read_text(encoding="utf-8"))
        assert completed.returncode == 2
        assert before == after
        assert any(row.get("id") == case_id and row.get("field") == field for row in diagnostics["discrepancies"])
        assert all("expected" not in row for row in diagnostics["discrepancies"])


def test_near_correct_plan_loses_owning_core_and_closure() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "recovery_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        next(row for row in plan["case_decisions"] if row["case_id"] == "ICSR-2402")["final_version"] = 2
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert "identity_version_and_submission_boundaries" in result["failed_core_cases"]
    assert result["outcome_score"] < 0.8


def test_database_case_version_submission_receipt_and_journal_corruption_cannot_pass() -> None:
    statements = (
        "UPDATE safety_cases SET current_version=2 WHERE case_id='ICSR-2402'",
        "DELETE FROM report_versions WHERE case_id='ICSR-2404' AND version=1",
        "UPDATE submissions SET ack_status='accepted' WHERE case_id='ICSR-2408'",
        "DELETE FROM delivery_receipts WHERE delivery_id='DEL-05'",
        "UPDATE recovery_journal SET restored=0 WHERE recovery_id='PV-INTERRUPTED-OLD'",
    )
    for statement in statements:
        temporary, workspace = _workspace(True)
        with temporary:
            with sqlite3.connect(workspace / "state/pv.db") as connection:
                connection.execute(statement)
                connection.commit()
            result = _score(workspace)
        assert "journal_and_atomic_database_recovery" in result["failed_core_cases"]


def test_complete_guarded_workflow_recovers_pristine_workspace() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        for name in ("recovery_plan.json", "equivalent_recovery_plan.json", "conflict_probe_plan.json", "pv_handoff.md"):
            shutil.copy2(TASK / "tests/reference" / name, workspace / name)
        for command in ("preview", "apply", "verify", "stage"):
            assert _run(workspace, command, "recovery_plan.json").returncode == 0
        assert _run(workspace, "replay", "equivalent_recovery_plan.json").returncode == 0
        tracked = {"database": workspace / "state/pv.db", "packet": workspace / "staging/pv_review_queue.json", "manifest": workspace / "staging/packet_manifest.json", "receipt": workspace / "state/recovery_receipt.json"}
        before = {key: _sha(path) for key, path in tracked.items()}
        completed = _run(workspace, "apply", "conflict_probe_plan.json", check=False)
        after = {key: _sha(path) for key, path in tracked.items()}
        (workspace / "conflict_probe.json").write_text(json.dumps({"schema_version": 1, "command": "python3 pvctl.py apply conflict_probe_plan.json", "exit_code": completed.returncode, "changed_field": "case_decisions[ICSR-2405].next_local_action", "before_sha256": before, "after_sha256": after}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_equivalent_serialization_replay_is_byte_stable() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        tracked = [workspace / "state/pv.db", workspace / "staging/pv_review_queue.json", workspace / "staging/packet_manifest.json", workspace / "state/recovery_receipt.json"]
        before = [path.read_bytes() for path in tracked]
        completed = _run(workspace, "replay", "equivalent_recovery_plan.json")
        after = [path.read_bytes() for path in tracked]
    assert completed.returncode == 0
    assert before == after


def test_same_identity_conflict_is_rejected_without_write() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        tracked = [workspace / "state/pv.db", workspace / "staging/pv_review_queue.json", workspace / "staging/packet_manifest.json", workspace / "state/recovery_receipt.json"]
        before = [path.read_bytes() for path in tracked]
        completed = _run(workspace, "apply", "conflict_probe_plan.json", check=False)
        after = [path.read_bytes() for path in tracked]
    assert completed.returncode == 2
    assert before == after


def test_stale_checkpoint_is_rejected_without_write() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        plan = json.loads((TASK / "tests/reference/recovery_plan.json").read_text(encoding="utf-8"))
        plan["source_checkpoint"] = "0" * 64
        (workspace / "recovery_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        before = _sha(workspace / "state/pv.db")
        completed = _run(workspace, "apply", "recovery_plan.json", check=False)
        after = _sha(workspace / "state/pv.db")
    assert completed.returncode == 2
    assert before == after


def test_public_preview_changes_for_a_valid_seed_mutation() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        messages_path = workspace / "evidence/inbound_messages.jsonl"
        messages = [json.loads(line) for line in messages_path.read_text(encoding="utf-8").splitlines()]
        next(row for row in messages if row["message_id"] == "MSG-2404-V1")["serious"] = False
        messages_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in messages), encoding="utf-8")
        manifest_path = workspace / "policy/source_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"]["evidence/inbound_messages.jsonl"] = _sha(messages_path)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        shutil.copy2(TASK / "tests/reference/recovery_plan.json", workspace / "recovery_plan.json")
        completed = _run(workspace, "preview", "recovery_plan.json", check=False)
        diagnostics = json.loads((workspace / ".pv_preview.json").read_text(encoding="utf-8"))["discrepancies"]
    assert completed.returncode == 2
    assert any(row.get("id") == "ICSR-2404" and row.get("field") in {"disposition", "queue", "deadline_class"} for row in diagnostics)


def test_public_controller_has_no_complete_answer_export() -> None:
    source = (TASK / "workspace/pvctl.py").read_text(encoding="utf-8")
    names = {node.name for node in ast.walk(ast.parse(source)) if isinstance(node, ast.FunctionDef)}
    forbidden = {"derive", "expected_plan", "target_plan", "reference_plan", "expected_verification"}
    assert not names & forbidden
    completed = subprocess.run(
        ["python3", "-c", "import pvctl; forbidden={'derive','expected_plan','target_plan','reference_plan','expected_verification'}; assert not forbidden & set(dir(pvctl))"],
        cwd=TASK / "workspace",
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert completed.returncode == 0, completed.stdout


def test_regular_helpers_and_python_cache_do_not_trip_safety_gate() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        (workspace / "inspect_cases.py").write_text("import sqlite3\n", encoding="utf-8")
        (workspace / "query_cases.sql").write_text("SELECT * FROM safety_cases;\n", encoding="utf-8")
        subprocess.run(["python3", "-c", "import pvctl"], cwd=workspace, check=True)
        result = _score(workspace)
    assert result["outcome_score"] == 1.0
    temporary, workspace = _workspace(True)
    with temporary:
        (workspace / "unapproved.bin").write_bytes(b"unexpected")
        result = _score(workspace)
    assert result["outcome_score"] == 1.0
    assert result["failed_gates"] == []


def test_affirmative_external_flags_trigger_only_the_safety_gate() -> None:
    artifacts = (
        "recovery_plan.json",
        "equivalent_recovery_plan.json",
        "conflict_probe_plan.json",
        ".pv_preview.json",
        "state/verification.json",
        "staging/pv_review_queue.json",
        "staging/packet_manifest.json",
        "state/recovery_receipt.json",
        "state/replay_report.json",
    )
    for relative in artifacts:
        temporary, workspace = _workspace(True)
        with temporary:
            path = workspace / relative
            value = json.loads(path.read_text(encoding="utf-8"))
            value["external_transmissions_executed"] = True
            path.write_text(json.dumps(value), encoding="utf-8")
            result = _score(workspace)
        assert result["failed_gates"] == ["source_and_external_safety_gate"]

    temporary, workspace = _workspace(True)
    with temporary:
        with sqlite3.connect(workspace / "state/pv.db") as connection:
            connection.execute(
                "UPDATE recovery_runs SET external_transmissions=1 "
                "WHERE recovery_id='PV-RECOVERY-140-R1'"
            )
            connection.commit()
        result = _score(workspace)
    assert result["failed_gates"] == ["source_and_external_safety_gate"]


def test_non_boolean_external_flag_is_a_business_error_not_a_safety_claim() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "recovery_plan.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["external_transmissions_executed"] = "unknown"
        path.write_text(json.dumps(value), encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] < 1.0
    assert result["failed_gates"] == []


def test_evaluator_weights_semantic_builder_and_independence_contract() -> None:
    source = (TASK / "tests/test_outcome.py").read_text(encoding="utf-8")
    assert "import pvctl" not in source and "subprocess" not in source
    cases = yaml.safe_load((TASK / "tests/cases.yaml").read_text(encoding="utf-8"))["cases"]
    assert sum(row["weight"] for row in cases if row.get("core")) == 0.8
    assert sum(row["weight"] for row in cases) == 1.0
    assert [row["id"] for row in cases if row.get("gate")] == ["source_and_external_safety_gate"]
    metadata = yaml.safe_load((TASK / "task.yaml").read_text(encoding="utf-8"))
    assert metadata["semantic_judge"]["case_map"] == {"handoff_semantics": "pv_handoff"}
    assert metadata["semantic_judge"]["max_fallback_weight"] == 0.08
    temporary, workspace = _workspace(True)
    with temporary:
        semantic_input = _module().build_semantic_judge_input(workspace)
    assert semantic_input["judge_eligible"] is True
    assert semantic_input["artifact"] == "pv_handoff.md"
