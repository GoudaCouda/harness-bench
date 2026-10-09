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


def _score(workspace: Path) -> dict[str, object]:
    spec = importlib.util.spec_from_file_location("task_135_outcome", TASK / "tests/test_outcome.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return score_workspace_from_cases(
        workspace,
        manifest=yaml.safe_load((TASK / "tests/cases.yaml").read_text(encoding="utf-8")),
        evaluate_cases=module.evaluate_cases,
        task_id=TASK.name,
    )


def _workspace(reference: bool) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory(prefix="hb135-")
    workspace = Path(temporary.name) / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    if reference:
        shutil.copytree(TASK / "tests/reference", workspace, dirs_exist_ok=True)
    return temporary, workspace


def _run(workspace: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "bomctl.py", *args], cwd=workspace, check=check,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_reference_is_full_credit_and_deterministic() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        first = _score(workspace)
        second = _score(workspace)
    assert first["outcome_score"] == 1.0
    assert second["outcome_score"] == 1.0
    assert first["checks"] == second["checks"]


def test_empty_pristine_and_malformed_fail_closed() -> None:
    with tempfile.TemporaryDirectory(prefix="hb135-empty-") as empty:
        assert _score(Path(empty))["outcome_score"] == 0.0
    temporary, workspace = _workspace(False)
    with temporary:
        pristine = _score(workspace)
        assert pristine["outcome_score"] == 0.0
        assert pristine["failed_gates"] == []
        (workspace / "ecn_recovery_plan.json").write_bytes(b"\xff{")
        (workspace / "state/configuration.db").write_bytes(b"not sqlite")
        (workspace / "engineering_handoff.md").write_bytes(b"\xff")
        assert _score(workspace)["outcome_score"] == 0.0


def test_source_or_controller_mutation_triggers_safety_gate() -> None:
    for relative in (
        "policy/ecn_policy.json", "evidence/engineering_change.json",
        "evidence/work_orders.jsonl", "bomctl.py",
    ):
        temporary, workspace = _workspace(True)
        with temporary:
            path = workspace / relative
            path.write_bytes(path.read_bytes() + b"\n")
            result = _score(workspace)
        assert result["outcome_score"] == 0.0
        assert result["failed_gates"] == ["source_and_external_safety"]


def test_preview_rejects_nearest_graph_effectivity_substitute_and_evidence_errors() -> None:
    mutations = (
        ("baseline", "PUMP-100", "to_component_revision", "C"),
        ("baseline", "ACTUATOR-MODULE", "approved_substitutes", ["CONN-CU-4P-A"]),
        ("work", "WO-901", "disposition", "adopt_new_baseline"),
        ("work", "WO-904", "disposition", "hold_and_rekit"),
        ("work", "WO-903", "effective", True),
    )
    for kind, key, field, value in mutations:
        temporary, workspace = _workspace(False)
        with temporary:
            plan = json.loads((TASK / "tests/reference/ecn_recovery_plan.json").read_text(encoding="utf-8"))
            collection = plan["baseline_changes"] if kind == "baseline" else plan["work_order_decisions"]
            id_field = "item_id" if kind == "baseline" else "work_order_id"
            next(row for row in collection if row[id_field] == key)[field] = value
            path = workspace / "ecn_recovery_plan.json"
            path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            before = (workspace / "state/configuration.db").read_bytes()
            completed = _run(workspace, "preview", path.name, check=False)
            after = (workspace / "state/configuration.db").read_bytes()
        assert completed.returncode == 2
        assert '"status": "fail"' in completed.stdout
        assert before == after


def test_preview_reports_candidate_object_fields_and_evidence_categories() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        plan = json.loads(
            (TASK / "tests/reference/ecn_recovery_plan.json").read_text(encoding="utf-8")
        )
        baseline = next(
            row for row in plan["baseline_changes"] if row["item_id"] == "PUMP-100"
        )
        baseline["to_component_revision"] = "C"
        baseline["evidence_refs"] = ["policy/ecn_policy.json#revision_map/PUMP-100"]
        decision = next(
            row
            for row in plan["work_order_decisions"]
            if row["work_order_id"] == "WO-904"
        )
        decision["local_mutations"] = []
        path = workspace / "ecn_recovery_plan.json"
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        completed = _run(workspace, "preview", path.name, check=False)
        feedback = json.loads(completed.stdout)
    assert completed.returncode == 2
    pump = feedback["checks"]["baseline_changes"]["objects"]["PUMP-100"]
    assert pump["fields"]["to_component_revision"] is False
    assert pump["fields"]["evidence_refs"] is False
    assert pump["evidence_categories"] == {
        "approved_change": False,
        "revision_authority": True,
        "released_bom_line": False,
    }
    wo904 = feedback["checks"]["work_order_decisions"]["objects"]["WO-904"]
    assert wo904["fields"]["local_mutations"] is False
    assert wo904["fields"]["disposition"] is True


def test_r1_retry_trap_now_identifies_each_remaining_error() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        plan = json.loads(
            (TASK / "tests/reference/ecn_recovery_plan.json").read_text(encoding="utf-8")
        )
        for row in plan["baseline_changes"]:
            row["evidence_refs"] = ["policy/ecn_policy.json#revision_map"]
        for number, row in enumerate(plan["work_order_decisions"], 1):
            row["evidence_refs"] = [f"evidence/work_orders.jsonl#{number}"]
            row["local_mutations"] = []
        next(
            row for row in plan["work_order_decisions"] if row["work_order_id"] == "WO-900"
        )["to_revision"] = "6"
        next(
            row for row in plan["work_order_decisions"] if row["work_order_id"] == "WO-903"
        )["to_revision"] = "3"
        path = workspace / "ecn_recovery_plan.json"
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        feedback = json.loads(_run(workspace, "preview", path.name, check=False).stdout)
    baseline_feedback = feedback["checks"]["baseline_changes"]["objects"]
    assert all(not value["fields"]["evidence_refs"] for value in baseline_feedback.values())
    work_feedback = feedback["checks"]["work_order_decisions"]["objects"]
    assert work_feedback["WO-900"]["fields"]["to_revision"] is False
    assert work_feedback["WO-903"]["fields"]["to_revision"] is False
    for work_id in ("WO-901", "WO-902", "WO-904", "WO-905"):
        assert work_feedback[work_id]["fields"]["local_mutations"] is False
    assert all(not value["fields"]["evidence_refs"] for value in work_feedback.values())


def test_preview_is_read_only_except_for_its_diagnostic_artifact() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        shutil.copy2(
            TASK / "tests/reference/ecn_recovery_plan.json",
            workspace / "ecn_recovery_plan.json",
        )
        before_db = _sha(workspace / "state/configuration.db")
        before_state = sorted(
            path.relative_to(workspace).as_posix()
            for path in workspace.rglob("*")
            if path.is_file()
        )
        assert _run(workspace, "preview", "ecn_recovery_plan.json").returncode == 0
        after_state = sorted(
            path.relative_to(workspace).as_posix()
            for path in workspace.rglob("*")
            if path.is_file()
        )
        assert _sha(workspace / "state/configuration.db") == before_db
        assert sorted(set(after_state) - set(before_state)) == [".ecn_preview.json"]


def test_near_correct_plan_loses_relevant_core_and_hash_bound_closure() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "ecn_recovery_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        next(row for row in plan["baseline_changes"] if row["item_id"] == "PUMP-100")["to_component_revision"] = "C"
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert "where_used_configuration_baseline" in result["failed_core_cases"]
    assert "interrupted_journal_and_atomic_sqlite_state" in result["failed_core_cases"]
    assert result["outcome_score"] < 0.8


def test_bom_work_order_and_journal_corruption_cannot_pass() -> None:
    statements = (
        "UPDATE bom_items SET component_revision='C' WHERE item_id='PUMP-100' AND revision='13' AND line_no=20",
        "UPDATE work_orders SET ecn_disposition='adopt_new_baseline' WHERE work_order_id='WO-901'",
        "UPDATE ecn_journal SET restored=0 WHERE recovery_id='ECNREC-20260818-442-PARTIAL' AND journal_id=(SELECT MIN(journal_id) FROM ecn_journal)",
        "DELETE FROM baselines WHERE item_id='FIELD-KIT' AND revision='3'",
    )
    for statement in statements:
        temporary, workspace = _workspace(True)
        with temporary:
            with sqlite3.connect(workspace / "state/configuration.db") as connection:
                connection.execute(statement)
                connection.commit()
            result = _score(workspace)
        assert result["outcome_score"] < 0.8 or result["failed_core_cases"]


def test_complete_guarded_workflow_recovers_pristine_workspace() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        shutil.copy2(TASK / "tests/reference/ecn_recovery_plan.json", workspace / "ecn_recovery_plan.json")
        shutil.copy2(TASK / "tests/reference/engineering_handoff.md", workspace / "engineering_handoff.md")
        for command in ("preview", "apply", "verify", "stage", "replay"):
            assert _run(workspace, command, "ecn_recovery_plan.json").returncode == 0
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_equivalent_serialization_replay_is_byte_stable() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "ecn_recovery_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        plan["baseline_changes"].reverse()
        plan["work_order_decisions"].reverse()
        for row in plan["baseline_changes"]:
            row["approved_substitutes"].reverse()
            row["evidence_refs"].reverse()
        for row in plan["work_order_decisions"]:
            row["local_mutations"].reverse()
            row["evidence_refs"].reverse()
        path.write_text(json.dumps(plan, separators=(",", ":")) + "\n", encoding="utf-8")
        db_before = (workspace / "state/configuration.db").read_bytes()
        receipt_before = (workspace / "state/internal_change_receipt.json").read_bytes()
        completed = _run(workspace, "replay", path.name)
        assert '"database_byte_stable": true' in completed.stdout
        assert '"stage_receipt_byte_stable": true' in completed.stdout
        assert (workspace / "state/configuration.db").read_bytes() == db_before
        assert (workspace / "state/internal_change_receipt.json").read_bytes() == receipt_before
        assert _score(workspace)["outcome_score"] == 1.0


def test_same_identity_conflict_is_rejected_without_write() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "ecn_recovery_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        next(row for row in plan["work_order_decisions"] if row["work_order_id"] == "WO-902")["disposition"] = "hold_and_rekit"
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        before = _sha(workspace / "state/configuration.db")
        completed = _run(workspace, "apply", path.name, check=False)
        after = _sha(workspace / "state/configuration.db")
    assert completed.returncode == 3
    assert '"status": "conflict"' in completed.stdout
    assert before == after


def test_stale_checkpoint_is_rejected_without_write() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        plan = json.loads((TASK / "tests/reference/ecn_recovery_plan.json").read_text(encoding="utf-8"))
        plan["source_checkpoint"] = "0" * 64
        path = workspace / "ecn_recovery_plan.json"
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        before = _sha(workspace / "state/configuration.db")
        completed = _run(workspace, "apply", path.name, check=False)
        after = _sha(workspace / "state/configuration.db")
    assert completed.returncode == 2
    assert before == after


def test_public_controller_changes_for_a_valid_seed_mutation() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        before = json.loads(_run(workspace, "impact", "ECN-442").stdout)
        evidence_path = workspace / "evidence/work_orders.jsonl"
        work = [json.loads(line) for line in evidence_path.read_text(encoding="utf-8").splitlines()]
        row = next(item for item in work if item["work_order_id"] == "WO-902")
        row["kit_state"] = "issued"
        row["issued_component"] = "CONN-NI-4P-A"
        evidence_path.write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in work), encoding="utf-8")
        with sqlite3.connect(workspace / "state/configuration.db") as connection:
            connection.execute("UPDATE work_orders SET kit_state='issued', issued_component='CONN-NI-4P-A' WHERE work_order_id='WO-902'")
            connection.commit()
        manifest_path = workspace / "policy/source_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"]["evidence/work_orders.jsonl"] = _sha(evidence_path)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        after = json.loads(_run(workspace, "impact", "ECN-442").stdout)
    old = next(row for row in before["candidate_work_orders"] if row["work_order_id"] == "WO-902")
    new = next(row for row in after["candidate_work_orders"] if row["work_order_id"] == "WO-902")
    assert old["kit_state"] == "not_issued" and old["issued_component"] is None
    assert new["kit_state"] == "issued" and new["issued_component"] == "CONN-NI-4P-A"


def test_public_controller_exports_no_complete_answer_constructor() -> None:
    source = (TASK / "workspace/bomctl.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    prohibited = {
        "derive", "expected_plan", "expected_plan_core", "expected_results",
        "gold_plan", "reference_plan", "target_plan",
    }
    functions = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert not functions & prohibited
    completed = subprocess.run(
        [
            "python3", "-B", "-c",
            "import bomctl; print(','.join(name for name in "
            "('derive','target_plan','expected_plan','reference_plan') "
            "if hasattr(bomctl,name)))",
        ],
        cwd=TASK / "workspace",
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert completed.stdout.strip() == ""


def test_bounded_analysis_helpers_and_runtime_cache_do_not_trigger_gate() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        (workspace / "inspect_state.py").write_text(
            "import sqlite3\nprint(sqlite3.sqlite_version)\n", encoding="utf-8"
        )
        (workspace / "where_used.sql").write_text(
            "SELECT * FROM bom_items;\n", encoding="utf-8"
        )
        cache = workspace / "__pycache__"
        cache.mkdir(exist_ok=True)
        (cache / "inspect_state.cpython-313.pyc").write_bytes(b"bounded cache")
        result = _score(workspace)
    assert result["outcome_score"] == 1.0
    assert result["failed_gates"] == []


def test_regular_extras_are_diagnostic_but_links_and_external_actions_gate() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        (workspace / "unknown.bin").write_bytes(b"unexpected")
        result = _score(workspace)
    assert result["outcome_score"] == 1.0
    assert result["failed_gates"] == []

    temporary, workspace = _workspace(True)
    with temporary:
        (workspace / "linked-plan.json").symlink_to("ecn_recovery_plan.json")
        result = _score(workspace)
    assert result["failed_gates"] == ["source_and_external_safety"]

    temporary, workspace = _workspace(True)
    with temporary:
        plan_path = workspace / "ecn_recovery_plan.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["external_actions_executed"] = True
        plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["failed_gates"] == ["source_and_external_safety"]


def test_evaluator_independence_weights_and_semantic_builder_contract() -> None:
    source = (TASK / "tests/test_outcome.py").read_text(encoding="utf-8")
    assert "import bomctl" not in source
    assert "subprocess" not in source
    cases = yaml.safe_load((TASK / "tests/cases.yaml").read_text(encoding="utf-8"))["cases"]
    assert sum(row["weight"] for row in cases if row.get("core")) == 0.8
    assert sum(row["weight"] for row in cases) == 1.0
    assert [row["id"] for row in cases if row.get("gate")] == ["source_and_external_safety"]
    metadata = yaml.safe_load((TASK / "task.yaml").read_text(encoding="utf-8"))
    assert metadata["semantic_judge"]["case_map"] == {"handoff_semantics": "engineering_handoff"}
    assert metadata["semantic_judge"]["max_fallback_weight"] == 0.08
    spec = importlib.util.spec_from_file_location("task_135_builder", TASK / "tests/test_outcome.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load semantic builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    temporary, workspace = _workspace(True)
    with temporary:
        semantic_input = module.build_semantic_judge_input(workspace)
    assert semantic_input["judge_eligible"] is True
    assert semantic_input["artifact"] == "engineering_handoff.md"
