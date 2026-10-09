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

import pytest
import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases


TASK = Path(__file__).resolve().parents[2]


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _score(workspace: Path) -> dict[str, object]:
    spec = importlib.util.spec_from_file_location("task_132_outcome", TASK / "tests/test_outcome.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return score_workspace_from_cases(workspace, manifest=yaml.safe_load((TASK / "tests/cases.yaml").read_text(encoding="utf-8")), evaluate_cases=module.evaluate_cases, task_id=TASK.name)


def _workspace(reference: bool) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory(prefix="hb132-")
    workspace = Path(temporary.name) / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    if reference:
        shutil.copytree(TASK / "tests/reference", workspace, dirs_exist_ok=True)
    return temporary, workspace


def _run(workspace: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["python3", "tripctl.py", *args], cwd=workspace, check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def _file_hash(path: Path) -> str:
    return _digest(path.read_bytes())


def _case(result: dict[str, object], case_id: str) -> dict[str, object]:
    return next(
        row
        for row in result["checks"]  # type: ignore[union-attr]
        if row["id"] == f"case:{case_id}"
    )


def test_reference_is_full_credit_and_deterministic() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        first = _score(workspace)
        second = _score(workspace)
    assert first["outcome_score"] == second["outcome_score"] == 1.0
    assert first["checks"] == second["checks"]


def test_seed_is_interrupted_and_distinct_from_reference_final() -> None:
    seed = TASK / "workspace/state/travel.db"
    final = TASK / "tests/reference/state/travel.db"
    assert _file_hash(seed) != _file_hash(final)
    with sqlite3.connect(seed) as connection:
        interrupted = connection.execute(
            "SELECT status FROM recovery_runs WHERE recovery_id=?",
            ("TRIP-20261015-FIRST-INTERRUPTED",),
        ).fetchone()
        current = connection.execute(
            "SELECT state,inventory_object FROM itinerary_objects WHERE object_id='AIR-2'"
        ).fetchone()
    assert interrupted == ("interrupted",)
    assert current == ("interrupted_candidate:OD-2", "OD-2")


def test_reference_builder_is_seed_isolated_and_repeatable() -> None:
    with tempfile.TemporaryDirectory(prefix="hb132-builder-") as temporary:
        task = Path(temporary) / TASK.name
        shutil.copytree(TASK, task)
        seed = task / "workspace/state/travel.db"
        before = _file_hash(seed)
        command = ["python3", "tests/ground_truth/build_reference.py"]
        subprocess.run(command, cwd=task, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        first_reference = _file_hash(task / "tests/reference/state/travel.db")
        assert _file_hash(seed) == before
        subprocess.run(command, cwd=task, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        assert _file_hash(seed) == before
        assert _file_hash(task / "tests/reference/state/travel.db") == first_reference
        assert first_reference != before


def test_empty_pristine_and_malformed_fail_closed() -> None:
    with tempfile.TemporaryDirectory(prefix="hb132-empty-") as empty:
        assert _score(Path(empty))["outcome_score"] == 0.0
    temporary, workspace = _workspace(False)
    with temporary:
        assert _score(workspace)["outcome_score"] == 0.0
        (workspace / "replan_plan.json").write_bytes(b"\xffnot-json")
        (workspace / "state/travel.db").write_bytes(b"not-sqlite")
        (workspace / "replan_handoff.md").write_bytes(b"\xff")
        assert _score(workspace)["outcome_score"] == 0.0


def test_oracle_score_vector_is_zero_zero_zero_one() -> None:
    with tempfile.TemporaryDirectory(prefix="hb132-empty-oracle-") as empty:
        empty_score = _score(Path(empty))["outcome_score"]
    temporary, pristine = _workspace(False)
    with temporary:
        pristine_score = _score(pristine)["outcome_score"]
    temporary, malformed = _workspace(False)
    with temporary:
        (malformed / "replan_plan.json").write_text("{}\n", encoding="utf-8")
        malformed_score = _score(malformed)["outcome_score"]
    temporary, reference = _workspace(True)
    with temporary:
        reference_score = _score(reference)["outcome_score"]
    assert [empty_score, pristine_score, malformed_score, reference_score] == [0.0, 0.0, 0.0, 1.0]


def test_preview_is_no_write_for_seed_database() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        shutil.copy2(TASK / "tests/reference/replan_plan.json", workspace / "replan_plan.json")
        before = _file_hash(workspace / "state/travel.db")
        completed = _run(workspace, "preview", "replan_plan.json")
        after = _file_hash(workspace / "state/travel.db")
    assert completed.returncode == 0
    assert before == after


def test_source_mutation_and_external_claim_trigger_gate() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        source = workspace / "evidence/disruption_events.jsonl"
        source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_input_integrity"]
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "replan_handoff.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nWe booked the replacement and submitted the refund.\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.0


def test_each_option_error_loses_its_own_case_without_unrelated_cliff() -> None:
    mutations = [("O-D", "violations", []), ("O-E", "feasible", True), ("O-G", "violations", ["checked_bag_recheck_not_permitted"]), ("O-I", "feasible", True), ("O-H", "reviewed_air_legs_changed", 1)]
    for option_id, field, value in mutations:
        temporary, workspace = _workspace(True)
        with temporary:
            path = workspace / "replan_plan.json"
            plan = json.loads(path.read_text(encoding="utf-8"))
            next(row for row in plan["option_assessments"] if row["option_id"] == option_id)[field] = value
            path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            result = _score(workspace)
        assert "option_assessments" in result["failed_core_cases"]
        assert _case(result, "option_assessments")["detail"] == {
            "failed_option_ids": [option_id]
        }
        assert "source_and_event_authority" not in result["failed_core_cases"]
        assert float(result["outcome_score"]) >= 0.68


def test_minimal_delta_and_database_are_independently_checked() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "replan_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        next(row for row in plan["object_decisions"] if row["object_id"] == "HOTEL")["action"] = "replace"
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert "object_decisions_and_projection" in result["failed_core_cases"]
    assert _case(result, "object_decisions_and_projection")["detail"] == {
        "failed_object_ids": ["HOTEL"]
    }
    temporary, workspace = _workspace(True)
    with temporary:
        with sqlite3.connect(workspace / "state/travel.db") as connection:
            connection.execute("UPDATE itinerary_objects SET state='local_proposal_hold:OH-1' WHERE object_id='AIR-1'")
            connection.commit()
        result = _score(workspace)
    assert "object_decisions_and_projection" in result["failed_core_cases"]
    assert _case(result, "object_decisions_and_projection")["detail"] == {
        "failed_object_ids": ["AIR-1"]
    }


def test_stale_receipt_loses_only_closure_credit() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "state/stage_receipt.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["local_hold_tokens"]["AIR-2"] = "0" * 64
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.88
    assert result["failed_core_cases"] == []


def test_stale_verification_is_rejected_without_database_write() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "state/verification.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["source_checkpoint"] = "0" * 64
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        before = _file_hash(workspace / "state/travel.db")
        completed = _run(workspace, "stage", "replan_plan.json", check=False)
        after = _file_hash(workspace / "state/travel.db")
    assert completed.returncode != 0
    assert "verification is missing or stale" in completed.stdout
    assert before == after


def test_equivalent_order_and_json_format_replay_byte_stable() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "replan_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        plan["option_assessments"].reverse()
        plan["object_decisions"].reverse()
        plan["applied_event_ids"].reverse()
        for row in plan["option_assessments"]:
            row["violations"].reverse()
            row["evidence_refs"].reverse()
        for row in plan["object_decisions"]:
            row["evidence_refs"].reverse()
        path.write_text(json.dumps(plan, separators=(",", ":")) + "\n", encoding="utf-8")
        before = (workspace / "state/travel.db").read_bytes()
        _run(workspace, "replay", "replan_plan.json")
        _run(workspace, "replay", "replan_plan.json")
        after = (workspace / "state/travel.db").read_bytes()
        result = _score(workspace)
    assert before == after
    assert result["outcome_score"] == 1.0


def test_same_identity_conflict_is_rejected_without_mutation() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "replan_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        plan["selected_option_id"] = "O-H"
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        before = (workspace / "state/travel.db").read_bytes()
        completed = _run(workspace, "apply", "replan_plan.json", check=False)
        after = (workspace / "state/travel.db").read_bytes()
    assert completed.returncode != 0
    assert before == after


def test_signed_seed_mutation_invalidates_the_old_candidate_without_writing() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        inventory_path = workspace / "evidence/inventory_snapshot.json"
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        option = next(row for row in inventory["options"] if row["option_id"] == "O-H")
        option["segments"][0] = {"segment_id": "LEG-1", "mode": "air", "from": "BOS", "to": "JFK", "depart": "2026-10-15T08:00:00-04:00", "arrive": "2026-10-15T09:15:00-04:00", "reviewed_segment": True}
        option["segments"][1]["from"] = "JFK"
        option["segments"][1]["depart"] = "2026-10-15T11:10:00-04:00"
        trust = json.loads((workspace / "evidence/inventory_trust.json").read_text(encoding="utf-8"))
        payload = {key: value for key, value in inventory.items() if key not in {"key_id", "signature"}}
        inventory["signature"] = _digest(_canonical(payload) + trust["verification_material"].encode())
        inventory_path.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest_path = workspace / "policy/source_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"]["evidence/inventory_snapshot.json"] = _digest(inventory_path.read_bytes())
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        shutil.copy2(TASK / "tests/reference/replan_plan.json", workspace / "replan_plan.json")
        before = (workspace / "state/travel.db").read_bytes()
        completed = _run(workspace, "preview", "replan_plan.json", check=False)
        after = (workspace / "state/travel.db").read_bytes()
    assert completed.returncode != 0
    assert before == after
    assert "selected_option_id" in completed.stdout or "option_assessments" in completed.stdout


def test_public_controller_has_no_complete_answer_export() -> None:
    source = (TASK / "workspace/tripctl.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert not names & {"derive", "expected_plan", "target_plan", "reference_plan", "expected_verification"}
    completed = subprocess.run(
        [
            "python3", "-c",
            "import tripctl; forbidden={'derive','expected_plan','target_plan','reference_plan','expected_verification'}; assert not forbidden & set(dir(tripctl))",
        ],
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
        (workspace / "inspect_trip.py").write_text("import sqlite3\n", encoding="utf-8")
        (workspace / "query_trip.sql").write_text("SELECT * FROM itinerary_objects;\n", encoding="utf-8")
        subprocess.run(["python3", "-c", "import tripctl"], cwd=workspace, check=True)
        result = _score(workspace)
    assert result["outcome_score"] == 1.0
    temporary, workspace = _workspace(True)
    with temporary:
        (workspace / "unapproved.bin").write_bytes(b"ordinary candidate scratch data")
        result = _score(workspace)
    assert result["outcome_score"] == 1.0
    temporary, workspace = _workspace(True)
    with temporary:
        (workspace / "unsafe-link").symlink_to("replan_plan.json")
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_input_integrity"]


def test_evaluator_is_independent_and_runner_contracts_hold() -> None:
    source = (TASK / "tests/test_outcome.py").read_text(encoding="utf-8")
    assert "import tripctl" not in source and "from tripctl" not in source
    assert "importlib" not in source and "subprocess" not in source
    cases = yaml.safe_load((TASK / "tests/cases.yaml").read_text(encoding="utf-8"))["cases"]
    assert sum(row["weight"] for row in cases if row.get("core")) == pytest.approx(0.8)
    assert sum(row["weight"] for row in cases) == pytest.approx(1.0)
    assert [row["id"] for row in cases if row.get("gate")] == ["safety_and_input_integrity"]
    metadata = yaml.safe_load((TASK / "task.yaml").read_text(encoding="utf-8"))
    assert metadata["semantic_judge"]["max_fallback_weight"] == 0.08
    spec = importlib.util.spec_from_file_location("task_132_builder", TASK / "tests/test_outcome.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load semantic builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    temporary, workspace = _workspace(True)
    with temporary:
        semantic_input = module.build_semantic_judge_input(workspace)
    assert semantic_input["judge_eligible"] is True
    assert semantic_input["artifact"] == "replan_handoff.md"
