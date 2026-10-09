from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import ast
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases


TASK = Path(__file__).resolve().parents[2]


def _score(workspace: Path) -> dict[str, object]:
    spec = importlib.util.spec_from_file_location("task_143_outcome", TASK / "tests/test_outcome.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return score_workspace_from_cases(
        workspace,
        manifest=yaml.safe_load((TASK / "tests/cases.yaml").read_text(encoding="utf-8")),
        evaluate_cases=module.evaluate_cases,
        task_id=TASK.name,
    )


def _workspace(reference: bool) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory(prefix="hb143-")
    workspace = Path(temporary.name) / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    if reference:
        shutil.copytree(TASK / "tests/reference", workspace, dirs_exist_ok=True)
    return temporary, workspace


def _run(workspace: Path, command: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "waterctl.py", command, "isolation_recovery_plan.json"],
        cwd=workspace, check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )


def test_reference_is_full_credit_and_deterministic() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        first = _score(workspace)
        second = _score(workspace)
    assert first["outcome_score"] == 1.0
    assert second["outcome_score"] == 1.0
    assert first["checks"] == second["checks"]


def test_empty_pristine_and_malformed_are_zero() -> None:
    with tempfile.TemporaryDirectory(prefix="hb143-empty-") as empty:
        assert _score(Path(empty))["outcome_score"] == 0.0
    temporary, workspace = _workspace(False)
    with temporary:
        assert _score(workspace)["outcome_score"] == 0.0
        (workspace / "isolation_recovery_plan.json").write_bytes(b"\xffbad")
        (workspace / "state/network.db").write_bytes(b"not sqlite")
        (workspace / "isolation_handoff.md").write_bytes(b"\xff")
        assert _score(workspace)["outcome_score"] == 0.0


def test_adjacent_plan_errors_are_object_attributed() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "isolation_recovery_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        next(row for row in plan["valve_decisions"] if row["valve_id"] == "V-02")["reason_codes"] = []
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert "boundary_selection_and_valve_dispositions" in result["failed_core_cases"]
    assert "telemetry_identity_and_sequence_authority" not in result["failed_core_cases"]

    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "isolation_recovery_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        next(row for row in plan["delivery_dispositions"] if row["delivery_id"] == "D-002")["disposition"] = "apply_observation"
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert "telemetry_identity_and_sequence_authority" in result["failed_core_cases"]
    assert "boundary_selection_and_valve_dispositions" not in result["failed_core_cases"]


def test_preview_is_read_only_and_feedback_is_object_specific() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        shutil.copy2(TASK / "tests/reference/isolation_recovery_plan.json", workspace / "isolation_recovery_plan.json")
        before = (workspace / "state/network.db").read_bytes()
        assert _run(workspace, "preview").returncode == 0
        assert before == (workspace / "state/network.db").read_bytes()
        plan = json.loads((workspace / "isolation_recovery_plan.json").read_text(encoding="utf-8"))
        next(row for row in plan["valve_decisions"] if row["valve_id"] == "V-05")["reason_codes"] = []
        next(row for row in plan["delivery_dispositions"] if row["delivery_id"] == "D-011")["disposition"] = "apply_observation"
        (workspace / "isolation_recovery_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        assert _run(workspace, "preview", check=False).returncode == 1
        assert before == (workspace / "state/network.db").read_bytes()
        feedback = json.loads((workspace / ".isolation_preview.json").read_text(encoding="utf-8"))
    assert "reason_codes" in feedback["valve_diagnostics"]["V-05"]["mismatches"]
    assert "disposition" in feedback["delivery_diagnostics"]["D-011"]["mismatches"]


def test_guarded_flow_from_pristine_closes_to_full_credit() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        shutil.copy2(TASK / "tests/reference/isolation_recovery_plan.json", workspace / "isolation_recovery_plan.json")
        shutil.copy2(TASK / "tests/reference/isolation_handoff.md", workspace / "isolation_handoff.md")
        for command in ("preview", "apply", "verify", "stage", "replay"):
            _run(workspace, command)
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_database_only_neighbor_error_loses_atomicity_core() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        with sqlite3.connect(workspace / "state/network.db") as con:
            con.execute("UPDATE valve_projections SET disposition='preserve_open' WHERE recovery_id='WIR-20260819-01' AND valve_id='V-03'")
            con.commit()
        result = _score(workspace)
    assert result["outcome_score"] == 0.72
    assert result["failed_core_cases"] == ["journal_atomicity_and_protected_state"]


def test_equivalent_replay_is_semantic_and_byte_stable() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "isolation_recovery_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        plan["valve_decisions"].reverse()
        plan["delivery_dispositions"].reverse()
        for row in plan["valve_decisions"]:
            for field in ("reason_codes", "impacted_zone_ids", "local_mutations", "evidence_refs"):
                row[field].reverse()
        for field in ("valves_to_close", "unavailable_valves", "protected_valves", "quarantined_deliveries"):
            plan["impact_summary"][field].reverse()
        path.write_text(json.dumps(plan, separators=(",", ":")) + "\n", encoding="utf-8")
        tracked = [workspace / "state/network.db", workspace / "state/recovery_receipt.json", workspace / "staging/isolation_review_packet.json", workspace / "staging/packet_manifest.json"]
        before = [item.read_bytes() for item in tracked]
        _run(workspace, "replay")
        _run(workspace, "replay")
        after = [item.read_bytes() for item in tracked]
        result = _score(workspace)
    assert before == after
    assert result["outcome_score"] == 1.0


def test_conflict_and_stale_checkpoint_fail_before_write() -> None:
    for mutation in ("conflict", "stale"):
        temporary, workspace = _workspace(True)
        with temporary:
            path = workspace / "isolation_recovery_plan.json"
            plan = json.loads(path.read_text(encoding="utf-8"))
            if mutation == "conflict":
                next(row for row in plan["valve_decisions"] if row["valve_id"] == "V-03")["next_local_action"] = "none"
            else:
                plan["source_checkpoint"] = "sha256:" + "0" * 64
            path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            before = (workspace / "state/network.db").read_bytes()
            completed = _run(workspace, "apply", check=False)
            after = (workspace / "state/network.db").read_bytes()
        assert completed.returncode == 2
        assert before == after


def test_seed_mutation_changes_derived_boundary() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        events_path = workspace / "evidence/telemetry_events.jsonl"
        rows = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
        for row in rows:
            if row["event_id"] == "EV-V02-3":
                row["payload"]["operability"] = "operable"
        events_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
        manifest_path = workspace / "policy/source_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"]["evidence/telemetry_events.jsonl"] = hashlib.sha256(events_path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        spec = importlib.util.spec_from_file_location("mutated_water_controller", workspace / "waterctl.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        plan_path = workspace / "isolation_recovery_plan.json"
        plan = json.loads((TASK / "tests/reference/isolation_recovery_plan.json").read_text(encoding="utf-8"))
        plan["source_checkpoint"] = module._source_checkpoint()
        plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        completed = _run(workspace, "preview", check=False)
        feedback = json.loads((workspace / ".isolation_preview.json").read_text(encoding="utf-8"))
    assert completed.returncode == 1
    assert "selected_boundary_id" in feedback["global_mismatches"]
    assert "impact_summary" in feedback["global_mismatches"]
    assert {"V-01", "V-02"}.issubset(feedback["valve_diagnostics"])


def test_source_tamper_and_external_claim_gate_but_regular_permissions_do_not() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "evidence/telemetry_events.jsonl"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        assert _score(workspace)["outcome_score"] == 0.0

    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "isolation_handoff.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nWe closed V-03 and notified the hospital.\n", encoding="utf-8")
        assert _score(workspace)["outcome_score"] == 0.0

    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "isolation_handoff.md"
        os.chmod(path, 0o666)
        assert _score(workspace)["outcome_score"] == 1.0


def test_evaluator_is_independent_and_semantic_input_is_bounded() -> None:
    source = (TASK / "tests/test_outcome.py").read_text(encoding="utf-8")
    assert "import waterctl" not in source
    assert "exec_module" not in source
    assert "subprocess" not in source
    spec = importlib.util.spec_from_file_location("task_143_semantic", TASK / "tests/test_outcome.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    temporary, workspace = _workspace(True)
    with temporary:
        payload = module.build_semantic_judge_input(workspace)
    assert payload["judge_eligible"] is True
    assert len(payload["text"]) <= 128 * 1024


def test_manifest_hashes_and_public_controller_has_no_final_map() -> None:
    manifest = json.loads((TASK / "workspace/policy/source_manifest.json").read_text(encoding="utf-8"))
    for relative, expected in manifest["files"].items():
        assert hashlib.sha256((TASK / "workspace" / relative).read_bytes()).hexdigest() == expected
    controller = (TASK / "workspace/waterctl.py").read_text(encoding="utf-8")
    assert "B-B" not in controller
    assert "V-02\": \"preserve_unavailable" not in controller
    assert "D-051\": \"quarantine_identity_collision" not in controller


def test_public_controller_has_no_complete_answer_constructor() -> None:
    source = (TASK / "workspace/waterctl.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_names = {"target_plan", "expected_plan", "derive_plan", "build_plan", "reference_plan"}
    functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert not {node.name.lstrip("_") for node in functions} & forbidden_names
    for node in functions:
        for child in ast.walk(node):
            if not isinstance(child, ast.Return) or not isinstance(child.value, ast.Dict):
                continue
            keys = {key.value for key in child.value.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)}
            assert not {"valve_decisions", "delivery_dispositions"}.issubset(keys)
