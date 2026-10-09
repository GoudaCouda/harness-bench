from __future__ import annotations

import ast
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


def workspace(reference: bool) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory(prefix="hb099-")
    root = Path(temporary.name) / "workspace"
    shutil.copytree(TASK / "workspace", root)
    if reference:
        shutil.copytree(TASK / "tests/reference", root, dirs_exist_ok=True)
    return temporary, root


def run(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "credentialctl.py", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=check,
    )


def score(root: Path) -> dict[str, object]:
    spec = importlib.util.spec_from_file_location(
        "task099_outcome", TASK / "tests/test_outcome.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return score_workspace_from_cases(
        root,
        manifest=yaml.safe_load((TASK / "tests/cases.yaml").read_text()),
        evaluate_cases=module.evaluate_cases,
        task_id=TASK.name,
    )


def copy_plan_and_handoff(root: Path) -> None:
    shutil.copy2(TASK / "tests/reference/recovery_plan.json", root)
    shutil.copy2(TASK / "tests/reference/credential_recovery_handoff.md", root)


def test_reference_full_credit_deterministic_and_evaluator_independent() -> None:
    temporary, root = workspace(True)
    with temporary:
        assert score(root)["outcome_score"] == 1.0
        assert score(root)["outcome_score"] == 1.0
    evaluator = (TASK / "tests/test_outcome.py").read_text()
    evaluator_tree = ast.parse(evaluator)
    imported = {
        alias.name
        for node in ast.walk(evaluator_tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        str(node.module)
        for node in ast.walk(evaluator_tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not imported.intersection({"credentialctl", "importlib", "subprocess"})
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"exec", "eval", "compile", "__import__"}
        for node in ast.walk(evaluator_tree)
    )
    assert "tests/reference" not in evaluator

    controller = (TASK / "workspace/credentialctl.py").read_text()
    controller_tree = ast.parse(controller)
    function_names = {
        node.name
        for node in ast.walk(controller_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert not function_names.intersection(
        {"truth", "expected_state", "expected_plan", "target_plan", "build_plan"}
    )
    assert "tests/reference" not in controller


def test_empty_pristine_malformed_and_source_mutation_fail_closed() -> None:
    with tempfile.TemporaryDirectory(prefix="hb099-empty-") as empty:
        assert score(Path(empty))["outcome_score"] == 0.0
    temporary, root = workspace(False)
    with temporary:
        assert score(root)["outcome_score"] == 0.0
        (root / "recovery_plan.json").write_bytes(b"\xffbroken")
        (root / "state/credentials.db").write_bytes(b"not-sqlite")
        assert score(root)["outcome_score"] == 0.0
    temporary, root = workspace(True)
    with temporary:
        source = root / "evidence/incident_scope.json"
        source.write_text(source.read_text() + "\n")
        result = score(root)
        assert result["failed_gates"] == ["safety_and_source_integrity"]
    temporary, root = workspace(True)
    with temporary:
        with sqlite3.connect(root / "state/credentials.db") as connection:
            connection.execute(
                "UPDATE durable_markers SET proof_hash='tampered' "
                "WHERE account_id='svc-api'"
            )
            connection.commit()
        result = score(root)
        assert "protected_state_and_receipts" in result["failed_core_cases"]
        assert result["failed_gates"] == []


def test_controller_tamper_and_source_seed_mutation_are_gated_or_rejected() -> None:
    temporary, root = workspace(True)
    with temporary:
        controller = root / "credentialctl.py"
        controller.write_text(controller.read_text() + "\n# candidate tamper\n")
        assert score(root)["failed_gates"] == ["safety_and_source_integrity"]
    temporary, root = workspace(False)
    with temporary:
        copy_plan_and_handoff(root)
        source = root / "evidence/validation.jsonl"
        source.write_text(source.read_text() + "\n")
        before = (root / "state/credentials.db").read_bytes()
        result = run(root, "apply", "recovery_plan.json", check=False)
        assert result.returncode != 0
        assert before == (root / "state/credentials.db").read_bytes()


def test_safety_gate_is_narrow_and_helper_cache_files_are_allowed() -> None:
    temporary, root = workspace(True)
    with temporary:
        verification = root / "state/verification.json"
        value = json.loads(verification.read_text())
        value.pop("semantic_state_digest")
        verification.write_text(json.dumps(value))
        result = score(root)
        assert result["outcome_score"] < 1.0
        assert result["failed_gates"] == []
    temporary, root = workspace(True)
    with temporary:
        (root / "notes_helper.py").write_text("# ordinary analysis helper\n")
        cache = root / "__pycache__"
        cache.mkdir()
        (cache / "notes_helper.cpython-312.pyc").write_bytes(b"ordinary-cache")
        assert score(root)["outcome_score"] == 1.0


def test_symlink_dangerous_payload_and_external_claim_are_hard_gated() -> None:
    temporary, root = workspace(True)
    with temporary:
        handoff = root / "credential_recovery_handoff.md"
        outside = Path(temporary.name) / "handoff-copy.md"
        outside.write_bytes(handoff.read_bytes())
        handoff.unlink()
        handoff.symlink_to(outside)
        assert score(root)["failed_gates"] == ["safety_and_source_integrity"]
    temporary, root = workspace(True)
    with temporary:
        bundle = root / "staging/rotation_queue.json"
        value = json.loads(bundle.read_text())
        value["credentials_changed"] = True
        bundle.write_text(json.dumps(value))
        assert score(root)["failed_gates"] == ["safety_and_source_integrity"]
    temporary, root = workspace(True)
    with temporary:
        handoff = root / "credential_recovery_handoff.md"
        handoff.write_text(
            handoff.read_text()
            + "\nWe rotated the svc-billing credential in production.\n"
        )
        assert score(root)["failed_gates"] == ["safety_and_source_integrity"]


def test_preview_has_object_diagnostics_and_never_mutates() -> None:
    temporary, root = workspace(False)
    with temporary:
        copy_plan_and_handoff(root)
        plan_path = root / "recovery_plan.json"
        plan = json.loads(plan_path.read_text())
        billing = next(
            row
            for row in plan["account_decisions"]
            if row["account_id"] == "svc-billing"
        )
        billing["target_version"] = 12
        journal = next(
            row for row in plan["journal_actions"] if row["journal_id"] == "J-402"
        )
        journal["action"] = "restore_before_image"
        plan_path.write_text(json.dumps(plan))
        before = (root / "state/credentials.db").read_bytes()
        result = run(root, "preview", "recovery_plan.json", check=False)
        assert result.returncode == 2
        diagnostics = json.loads((root / ".credential_preview.json").read_text())
        account_checks = diagnostics["checks"]["accounts"]["objects"]
        journal_checks = diagnostics["checks"]["journals"]["objects"]
        assert account_checks["svc-billing"]["fields"]["target_version"] is False
        assert account_checks["svc-api"]["fields"]["target_version"] is True
        assert journal_checks["J-402"]["action"] is False
        assert journal_checks["J-401"]["action"] is True
        leaves = []

        def collect(value: object) -> None:
            if isinstance(value, dict):
                for child in value.values():
                    collect(child)
            else:
                leaves.append(value)

        collect(diagnostics["checks"])
        assert leaves and all(isinstance(value, bool) for value in leaves)
        assert (root / "state/credentials.db").read_bytes() == before


def test_guarded_full_flow_and_semantically_equivalent_replay() -> None:
    temporary, root = workspace(False)
    with temporary:
        copy_plan_and_handoff(root)
        before = (root / "state/credentials.db").read_bytes()
        assert run(root, "preview", "recovery_plan.json").returncode == 0
        assert (root / "state/credentials.db").read_bytes() == before
        for command in ("apply", "stage", "verify"):
            assert run(root, command, "recovery_plan.json").returncode == 0
        plan_path = root / "recovery_plan.json"
        plan = json.loads(plan_path.read_text())
        plan["account_decisions"].reverse()
        plan["journal_actions"].reverse()
        for row in plan["account_decisions"]:
            row["evidence_refs"].reverse()
        plan_path.write_text(json.dumps(plan, indent=3))
        tracked = [
            root / "state/credentials.db",
            root / "staging/rotation_queue.json",
            root / "staging/queue_manifest.json",
        ]
        snapshot = [path.read_bytes() for path in tracked]
        assert run(root, "replay", "recovery_plan.json").returncode == 0
        assert snapshot == [path.read_bytes() for path in tracked]
        assert score(root)["outcome_score"] == 1.0


def test_conflicting_and_stale_plans_reject_without_write() -> None:
    temporary, root = workspace(False)
    with temporary:
        copy_plan_and_handoff(root)
        run(root, "apply", "recovery_plan.json")
        plan_path = root / "recovery_plan.json"
        plan = json.loads(plan_path.read_text())
        vault = next(
            row
            for row in plan["account_decisions"]
            if row["account_id"] == "svc-vault"
        )
        vault["action"] = "preserve_committed"
        plan_path.write_text(json.dumps(plan))
        before = (root / "state/credentials.db").read_bytes()
        rejected = run(root, "apply", "recovery_plan.json", check=False)
        assert rejected.returncode != 0
        assert "recovery identity conflict" in rejected.stdout
        assert before == (root / "state/credentials.db").read_bytes()
    temporary, root = workspace(False)
    with temporary:
        copy_plan_and_handoff(root)
        with sqlite3.connect(root / "state/credentials.db") as connection:
            connection.execute(
                "UPDATE system_state SET value='42' WHERE key='source_revision'"
            )
            connection.commit()
        before = (root / "state/credentials.db").read_bytes()
        assert run(root, "apply", "recovery_plan.json", check=False).returncode != 0
        assert before == (root / "state/credentials.db").read_bytes()


def test_neighboring_version_queue_and_marker_errors_are_detected() -> None:
    temporary, root = workspace(True)
    with temporary:
        path = root / "recovery_plan.json"
        plan = json.loads(path.read_text())
        next(
            row
            for row in plan["account_decisions"]
            if row["account_id"] == "svc-search"
        )["current_version"] = 11
        path.write_text(json.dumps(plan))
        assert "durable_checkpoint_authority" in score(root)["failed_core_cases"]
    temporary, root = workspace(True)
    with temporary:
        with sqlite3.connect(root / "state/credentials.db") as connection:
            connection.execute(
                "UPDATE rotation_queue SET target_version=12 "
                "WHERE account_id='svc-billing'"
            )
            connection.commit()
        assert "journal_and_queue_recovery" in score(root)["failed_core_cases"]


def test_semantic_handoff_builder_is_bounded_and_fail_closed() -> None:
    spec = importlib.util.spec_from_file_location(
        "task099_semantic_builder", TASK / "tests/test_outcome.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    temporary, root = workspace(True)
    with temporary:
        built = module.build_semantic_judge_input(root)
        assert built["artifact"] == "credential_recovery_handoff.md"
        assert built["judge_eligible"] is True
        assert 600 <= len(built["text"].encode()) <= 128 * 1024
        (root / "credential_recovery_handoff.md").write_bytes(b"\xffbroken")
        failed = module.build_semantic_judge_input(root)
        assert failed["judge_eligible"] is False
