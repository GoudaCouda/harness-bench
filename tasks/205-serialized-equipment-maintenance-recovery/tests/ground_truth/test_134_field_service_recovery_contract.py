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


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _module():
    spec = importlib.util.spec_from_file_location("task_134_outcome", TASK / "tests/test_outcome.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _score(workspace: Path) -> dict[str, object]:
    module = _module()
    return score_workspace_from_cases(
        workspace,
        manifest=yaml.safe_load((TASK / "tests/cases.yaml").read_text(encoding="utf-8")),
        evaluate_cases=module.evaluate_cases,
        task_id=TASK.name,
    )


def _workspace(reference: bool) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory(prefix="hb134-")
    workspace = Path(temporary.name) / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    if reference:
        shutil.copytree(TASK / "tests/reference", workspace, dirs_exist_ok=True)
    return temporary, workspace


def _run(workspace: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "maintenancectl.py", *args], cwd=workspace, check=check,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )


def test_reference_is_full_credit_and_deterministic() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        first = _score(workspace)
        second = _score(workspace)
    assert first["outcome_score"] == 1.0
    assert second["outcome_score"] == 1.0
    assert first["checks"] == second["checks"]


def test_empty_pristine_and_malformed_fail_closed() -> None:
    with tempfile.TemporaryDirectory(prefix="hb134-empty-") as empty:
        empty_result = _score(Path(empty))
        assert empty_result["outcome_score"] == 0.0
    temporary, workspace = _workspace(False)
    with temporary:
        pristine_result = _score(workspace)
        assert pristine_result["outcome_score"] == 0.0
        assert pristine_result["failed_gates"] == []
        (workspace / "maintenance_recovery_plan.json").write_bytes(b"\xffbad-json")
        (workspace / "state/maintenance.db").write_bytes(b"not-sqlite")
        (workspace / "maintenance_handoff.md").write_bytes(b"\xff")
        malformed_result = _score(workspace)
        assert malformed_result["outcome_score"] == 0.0
        assert malformed_result["failed_gates"] == []


def test_adjacent_plan_errors_lose_only_their_business_core() -> None:
    mutations = (
        ("WO-200", "selected_bom_revision", "PX8-R1", "incident_symptoms_bom_and_evidence", 0.85),
        ("WO-202", "disposition", "ready_local_dispatch", "controls_allocation_holds_and_totals", 0.82),
    )
    for work_order_id, field, value, failed_case, expected_score in mutations:
        temporary, workspace = _workspace(True)
        with temporary:
            path = workspace / "maintenance_recovery_plan.json"
            plan = json.loads(path.read_text(encoding="utf-8"))
            next(row for row in plan["assignments"] if row["work_order_id"] == work_order_id)[field] = value
            path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            result = _score(workspace)
        assert result["outcome_score"] == expected_score
        assert result["failed_core_cases"] == [failed_case]


def test_database_and_each_closure_artifact_are_independently_checked() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        with sqlite3.connect(workspace / "state/maintenance.db") as connection:
            connection.execute("UPDATE part_lots SET quantity=7 WHERE lot_id='LOT-B42-REL'")
            connection.commit()
        result = _score(workspace)
    assert result["outcome_score"] == 0.84
    assert result["failed_core_cases"] == ["resource_inventory_and_event_projection"]

    artifacts = (
        ".maintenance_preview.json", "state/verification.json",
        "staging/service_dispatch_bundle.json", "staging/dispatch_manifest.json",
        "state/recovery_receipt.json", "state/replay_report.json",
    )
    for relative in artifacts:
        temporary, workspace = _workspace(True)
        with temporary:
            path = workspace / relative
            value = json.loads(path.read_text(encoding="utf-8"))
            value["schema_version" if "schema_version" in value else "status"] = "tampered"
            path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
            result = _score(workspace)
        assert result["outcome_score"] == 0.88, relative
        assert result["failed_core_cases"] == []


def test_missing_closure_is_business_incompleteness_not_a_safety_gate() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        for relative in (
            ".maintenance_preview.json", "state/verification.json",
            "staging/service_dispatch_bundle.json", "staging/dispatch_manifest.json",
            "state/recovery_receipt.json", "state/replay_report.json",
        ):
            (workspace / relative).unlink()
        result = _score(workspace)
    assert result["outcome_score"] == 0.88
    assert result["failed_gates"] == []
    assert result["failed_core_cases"] == []


def test_source_and_protected_execution_mutations_trigger_gate() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "evidence/work_order_events.jsonl"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_input_integrity"]

    temporary, workspace = _workspace(True)
    with temporary:
        with sqlite3.connect(workspace / "state/maintenance.db") as connection:
            connection.execute("UPDATE work_orders SET executed_at=NULL WHERE work_order_id='WO-190'")
            connection.commit()
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_input_integrity"]


def test_equivalent_order_and_json_representation_replay_is_byte_stable() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "maintenance_recovery_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        plan["assignments"].reverse()
        plan["event_dispositions"].reverse()
        for row in plan["assignments"]:
            row["symptom_codes"].reverse()
            row["evidence_refs"].reverse()
        path.write_text(json.dumps(plan, separators=(",", ":")) + "\n", encoding="utf-8")
        tracked = [
            workspace / "state/maintenance.db",
            workspace / "staging/service_dispatch_bundle.json",
            workspace / "staging/dispatch_manifest.json",
            workspace / "state/recovery_receipt.json",
        ]
        before = [item.read_bytes() for item in tracked]
        _run(workspace, "replay", "maintenance_recovery_plan.json")
        _run(workspace, "replay", "maintenance_recovery_plan.json")
        after = [item.read_bytes() for item in tracked]
        result = _score(workspace)
    assert before == after
    assert result["outcome_score"] == 1.0


def test_same_identity_conflict_and_stale_checkpoint_reject_without_mutation() -> None:
    for field, value in (("source_checkpoint", "0" * 64),):
        temporary, workspace = _workspace(True)
        with temporary:
            path = workspace / "maintenance_recovery_plan.json"
            plan = json.loads(path.read_text(encoding="utf-8"))
            plan[field] = value
            path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            before = (workspace / "state/maintenance.db").read_bytes()
            completed = _run(workspace, "apply", "maintenance_recovery_plan.json", check=False)
            after = (workspace / "state/maintenance.db").read_bytes()
        assert completed.returncode != 0
        assert before == after

    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "maintenance_recovery_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        next(row for row in plan["assignments"] if row["work_order_id"] == "WO-200")["allocated_part_lot"] = "LOT-B42-QUAR"
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        before = (workspace / "state/maintenance.db").read_bytes()
        completed = _run(workspace, "apply", "maintenance_recovery_plan.json", check=False)
        after = (workspace / "state/maintenance.db").read_bytes()
    assert completed.returncode != 0
    assert before == after


def test_seed_mutation_changes_candidate_validation_without_answer_export() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        plan = json.loads((TASK / "tests/reference/maintenance_recovery_plan.json").read_text(encoding="utf-8"))
        path = workspace / "maintenance_recovery_plan.json"
        path.write_text(json.dumps(plan), encoding="utf-8")
        before = (workspace / "state/maintenance.db").read_bytes()
        with sqlite3.connect(workspace / "state/maintenance.db") as connection:
            connection.execute("UPDATE bom_effectivity SET part_number='BRG-42C' WHERE model='PX-8' AND component='drive_bearing' AND bom_revision='PX8-R2'")
            connection.execute("UPDATE part_lots SET part_number='BRG-42C' WHERE lot_id='LOT-B42-REL'")
            connection.commit()
        completed = _run(workspace, "preview", "maintenance_recovery_plan.json", check=False)
        report = json.loads((workspace / ".maintenance_preview.json").read_text(encoding="utf-8"))
        after = (workspace / "state/maintenance.db").read_bytes()
    assert completed.returncode == 2
    assert before != after  # seed mutation itself changed the authoritative test fixture
    assert any(item["id"] == "WO-200" and item["field"] == "required_part_number" for item in report["discrepancies"])
    assert all("expected" not in item and "actual" not in item for item in report["discrepancies"])


def test_evaluator_is_independent_and_controller_has_no_seed_answer_map() -> None:
    evaluator = (TASK / "tests/test_outcome.py").read_text(encoding="utf-8")
    assert "import maintenancectl" not in evaluator
    assert "from maintenancectl" not in evaluator
    assert "subprocess" not in evaluator
    assert "importlib" not in evaluator
    assert "tests/reference" not in evaluator
    controller = (TASK / "workspace/maintenancectl.py").read_text(encoding="utf-8")
    for literal in ("PKG-PX8-00041", "WO-200", "BRG-42B", "LOT-B42-REL", "TECH-A"):
        assert literal not in controller


def test_public_controller_exports_no_complete_answer_constructor() -> None:
    source = (TASK / "workspace/maintenancectl.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert not names & {"derive", "expected_plan", "target_plan", "reference_plan", "gold_plan"}
    for function in (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)):
        for returned in (node.value for node in ast.walk(function) if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)):
            keys = {key.value for key in returned.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)}
            assert not keys & {"plan", "decisions", "final_rows", "final_records"}
    completed = subprocess.run(
        ["python3", "-B", "-c", "import maintenancectl; assert not hasattr(maintenancectl, 'derive'); assert not hasattr(maintenancectl, 'target_plan')"],
        cwd=TASK / "workspace", check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    assert completed.returncode == 0


def test_preview_valid_and_invalid_are_read_only_with_object_feedback() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        plan = json.loads((TASK / "tests/reference/maintenance_recovery_plan.json").read_text(encoding="utf-8"))
        path = workspace / "maintenance_recovery_plan.json"
        path.write_text(json.dumps(plan), encoding="utf-8")
        before = (workspace / "state/maintenance.db").read_bytes()
        _run(workspace, "preview", "maintenance_recovery_plan.json")
        assert before == (workspace / "state/maintenance.db").read_bytes()
        next(row for row in plan["assignments"] if row["work_order_id"] == "WO-202")["instrument_id"] = "VIB-A"
        path.write_text(json.dumps(plan), encoding="utf-8")
        completed = _run(workspace, "preview", "maintenance_recovery_plan.json", check=False)
        report = json.loads((workspace / ".maintenance_preview.json").read_text(encoding="utf-8"))
        after = (workspace / "state/maintenance.db").read_bytes()
    assert completed.returncode == 2
    assert before == after
    assert any(item["id"] == "WO-202" and item["field"] == "instrument_id" for item in report["discrepancies"])
    assert all(set(item) == {"scope", "id", "field", "evidence"} for item in report["discrepancies"])
    assert all("expected" not in item and "actual" not in item and "value" not in item for item in report["discrepancies"])


def test_runtime_cache_and_bounded_helper_are_diagnostic_only() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        subprocess.run(["python3", "-c", "import maintenancectl"], cwd=workspace, check=True)
        (workspace / "dump_db.py").write_text("import sqlite3\n", encoding="utf-8")
        assert _score(workspace)["outcome_score"] == 1.0
        cache = workspace / "__pycache__"
        cache.mkdir(exist_ok=True)
        (cache / "payload.txt").write_text("not bytecode\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 1.0
    assert result["failed_gates"] == []


def test_semantic_builder_contract_paraphrase_stuffing_and_contradiction() -> None:
    module = _module()
    temporary, workspace = _workspace(True)
    with temporary:
        semantic_input = module.build_semantic_judge_input(workspace)
        assert semantic_input["judge_eligible"] is True
        assert semantic_input["artifact"] == "maintenance_handoff.md"

        paraphrase = """# Service recovery summary

The planner treated repeated vibration delivery number eight as a retransmission of the same event rather than a second fault. Observations were consumed in their recorded sequence. The later duplicate order for serialized line 41 was consolidated into its earlier open order, while the unknown order and the post-completion observation were excluded.

The incident date placed the drive bearing under the second PX8 service structure and its newer B-series bearing, never the superseded item. The first eligible rotating-equipment mechanic, an in-date vibration meter, and the sole released bearing lot make that order ready for local preparation. The PX9 electrical case stays blocked because its megohm meters are either past due or disabled even though the electrician and fuse are suitable. The belt case also stays blocked: its matching released stock is empty and the remaining stock is under quarantine despite an eligible conveyor mechanic and tachometer.

Before projecting those decisions, the interrupted before-state record was restored and the system committed once. One usable bearing moved from one available unit to none, with no second consumption. The historical completed bearing replacement retained its original asset, technician, lot, action, and completion time. The verification fingerprint, packet fingerprint, manifest, and local receipt all describe the same recovered state. A semantically identical resubmission changes no authoritative bytes, while a different plan under the same recovery identity is refused.

This is planning material only. Nobody has been sent to the site; inventory has not been reserved or fitted in an external system; no energy-isolation permit was performed; and the packaging line was not powered. All results remain local.
"""
        (workspace / "maintenance_handoff.md").write_text(paraphrase, encoding="utf-8")
        result = _score(workspace)
        semantic_input = module.build_semantic_judge_input(workspace)
        assert "maintenance_handoff" not in [check["id"].removeprefix("case:") for check in result["checks"] if check["pass"]]
        assert result["outcome_score"] == 0.92
        assert semantic_input["judge_eligible"] is True

        reference = (TASK / "tests/reference/maintenance_handoff.md").read_text(encoding="utf-8")
        first_sentence = reference.split(".", 1)[0] + "."
        (workspace / "maintenance_handoff.md").write_text((first_sentence + "\n") * 20 + reference, encoding="utf-8")
        assert _score(workspace)["outcome_score"] == 0.92

        (workspace / "maintenance_handoff.md").write_text(reference + "\nOur team dispatched TECH-A and installed the reserved bearing.\n", encoding="utf-8")
        contradiction = _score(workspace)
        assert contradiction["outcome_score"] == 0.0
        assert contradiction["failed_gates"] == ["safety_and_input_integrity"]

    temporary, workspace = _workspace(False)
    with temporary:
        missing = module.build_semantic_judge_input(workspace)
    assert missing["judge_eligible"] is False


def test_case_weights_and_semantic_configuration() -> None:
    cases = yaml.safe_load((TASK / "tests/cases.yaml").read_text(encoding="utf-8"))["cases"]
    assert sum(item["weight"] for item in cases if item.get("core")) == 0.8
    assert sum(item["weight"] for item in cases) == 1.0
    assert [item["id"] for item in cases if item.get("gate")] == ["safety_and_input_integrity"]
    metadata = yaml.safe_load((TASK / "task.yaml").read_text(encoding="utf-8"))
    assert metadata["semantic_judge"]["case_map"] == {"handoff_semantics": "maintenance_handoff"}
    assert metadata["semantic_judge"]["max_fallback_weight"] == 0.08
