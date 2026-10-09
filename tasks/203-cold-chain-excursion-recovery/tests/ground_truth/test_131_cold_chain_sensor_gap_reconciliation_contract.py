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


def _module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _score(workspace: Path) -> dict[str, object]:
    evaluator = _module(TASK / "tests/test_outcome.py", "task131_outcome")
    return score_workspace_from_cases(
        workspace,
        manifest=yaml.safe_load(
            (TASK / "tests/cases.yaml").read_text(encoding="utf-8")
        ),
        evaluate_cases=evaluator.evaluate_cases,
        task_id=TASK.name,
    )


def _workspace(
    reference: bool = False,
) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory(prefix="hb131-")
    workspace = Path(temporary.name) / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    if reference:
        shutil.copytree(TASK / "tests/reference", workspace, dirs_exist_ok=True)
    return temporary, workspace


def _run(
    workspace: Path, command: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "coldchainctl.py", command, "excursion_plan.json"],
        cwd=workspace,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def _check(result: dict[str, object], case_id: str) -> dict[str, object]:
    return next(
        item
        for item in result["checks"]
        if item["id"] == f"case:{case_id}"
    )


def test_reference_is_full_credit_and_deterministic() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        first, second = _score(workspace), _score(workspace)
    assert first["outcome_score"] == second["outcome_score"] == 1.0
    assert first["checks"] == second["checks"]


def test_empty_pristine_and_malformed_fail_closed() -> None:
    with tempfile.TemporaryDirectory(prefix="hb131-empty-") as empty:
        assert _score(Path(empty))["outcome_score"] == 0.0
    temporary, workspace = _workspace()
    with temporary:
        assert _score(workspace)["outcome_score"] == 0.0
        (workspace / "excursion_plan.json").write_bytes(b"\xffbad-json")
        (workspace / "state/cold_chain.db").write_bytes(b"bad-sqlite")
        (workspace / "cold_chain_handoff.md").write_bytes(b"\xff")
        assert _score(workspace)["outcome_score"] == 0.0


def test_source_mutation_and_executed_external_claim_trigger_gate() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        source = workspace / "evidence/logger_readings.jsonl"
        source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_source_integrity"]

    temporary, workspace = _workspace(True)
    with temporary:
        controller = workspace / "coldchainctl.py"
        controller.write_text(
            controller.read_text(encoding="utf-8") + "\n# candidate tamper\n",
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_source_integrity"]

    temporary, workspace = _workspace(True)
    with temporary:
        handoff = workspace / "cold_chain_handoff.md"
        handoff.write_text(
            handoff.read_text(encoding="utf-8")
            + "\nOur team destroyed the quarantined stock and notified recipients.\n",
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_source_integrity"]


def test_threshold_adjacent_wrong_disposition_loses_action_core() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "excursion_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        row = next(item for item in plan["decisions"] if item["lot_id"] == "LOT-AURORA")
        row["out_of_range_minutes"] = 10
        row["disposition"] = "available"
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.8
    assert result["failed_core_cases"] == ["aurora_excursion_resolution"]
    assert _check(result, "aurora_excursion_resolution")["detail"] == {
        "lot_id": "LOT-AURORA",
        "fields": ["disposition", "out_of_range_minutes"],
    }


def test_gap_fallback_and_calibration_neighbors_lose_authority_core() -> None:
    for field, value in (
        ("gap_intervals_utc", ["2026-11-01T05:40:00Z/2026-11-01T06:00:00Z"]),
        ("fallback_device_id", "S-B1"),
        ("fallback_calibration_id", "CAL-SB-OLD"),
    ):
        temporary, workspace = _workspace(True)
        with temporary:
            path = workspace / "excursion_plan.json"
            plan = json.loads(path.read_text(encoding="utf-8"))
            lot = "LOT-AURORA" if field == "gap_intervals_utc" else "LOT-BIRCH"
            next(item for item in plan["decisions"] if item["lot_id"] == lot)[field] = (
                value
            )
            path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            result = _score(workspace)
        expected_case = (
            "aurora_excursion_resolution"
            if field == "gap_intervals_utc"
            else "birch_evidence_gap_resolution"
        )
        assert result["outcome_score"] == 0.8
        assert result["failed_core_cases"] == [expected_case]
        assert _check(result, expected_case)["detail"] == {
            "lot_id": "LOT-AURORA" if field == "gap_intervals_utc" else "LOT-BIRCH",
            "fields": [field],
        }


def test_interrupted_journal_duration_and_conservation_are_real_state() -> None:
    temporary, pristine = _workspace()
    with temporary, sqlite3.connect(pristine / "state/cold_chain.db") as connection:
        assert (
            connection.execute(
                "SELECT disposition FROM lots WHERE lot_id='LOT-AURORA'"
            ).fetchone()[0]
            == "qa_hold"
        )
        assert (
            connection.execute("SELECT status FROM recovery_runs").fetchone()[0]
            == "interrupted"
        )
        assert (
            connection.execute("SELECT restored FROM recovery_journal").fetchone()[0]
            == 0
        )
    temporary, workspace = _workspace(True)
    with temporary, sqlite3.connect(workspace / "state/cold_chain.db") as connection:
        lots = connection.execute(
            "SELECT lot_id,quantity,disposition,do_not_use FROM lots ORDER BY lot_id"
        ).fetchall()
        assert sum(row[1] for row in lots) == 880
        assert lots == [
            ("LOT-AURORA", 420, "quarantine_do_not_use", 1),
            ("LOT-BIRCH", 160, "hold_evidence_gap", 0),
            ("LOT-CEDAR", 300, "available", 0),
        ]
        assert (
            connection.execute(
                "SELECT restored FROM recovery_journal WHERE recovery_id='CCR-INTERRUPTED-00'"
            ).fetchone()[0]
            == 1
        )
        duration = connection.execute(
            "SELECT out_of_range_minutes FROM excursion_assessments WHERE lot_id='LOT-AURORA'"
        ).fetchone()[0]
        assert duration == 20


def test_stale_checkpoint_rejected_before_write() -> None:
    temporary, workspace = _workspace()
    with temporary:
        plan = json.loads(
            (TASK / "tests/reference/excursion_plan.json").read_text(encoding="utf-8")
        )
        plan["source_checkpoint"] = "0" * 64
        (workspace / "excursion_plan.json").write_text(
            json.dumps(plan), encoding="utf-8"
        )
        before = (workspace / "state/cold_chain.db").read_bytes()
        result = _run(workspace, "apply", check=False)
        after = (workspace / "state/cold_chain.db").read_bytes()
    assert result.returncode != 0
    assert before == after
    assert '"source_checkpoint": false' in result.stdout


def test_equivalent_replay_is_stable_and_conflict_is_rejected() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "excursion_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        plan["decisions"].reverse()
        for row in plan["decisions"]:
            for field in ("gap_intervals_utc", "local_mutations", "evidence_refs"):
                row[field].reverse()
        path.write_text(
            json.dumps(plan, separators=(",", ":")) + "\n", encoding="utf-8"
        )
        before = (workspace / "state/cold_chain.db").read_bytes()
        assert _run(workspace, "replay").returncode == 0
        assert before == (workspace / "state/cold_chain.db").read_bytes()
        next(item for item in plan["decisions"] if item["lot_id"] == "LOT-BIRCH")[
            "disposition"
        ] = "available"
        path.write_text(json.dumps(plan), encoding="utf-8")
        conflict_before = (workspace / "state/cold_chain.db").read_bytes()
        conflict = _run(workspace, "apply", check=False)
        conflict_after = (workspace / "state/cold_chain.db").read_bytes()
    assert conflict.returncode != 0
    assert "semantic_plan_conflict" in conflict.stdout
    assert conflict_before == conflict_after


def test_signed_seed_mutation_is_validated_without_exporting_decisions() -> None:
    temporary, workspace = _workspace()
    with temporary:
        ctl = _module(workspace / "coldchainctl.py", "mutated_coldchainctl")
        path = workspace / "evidence/logger_readings.jsonl"
        rows = [
            json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        ]
        next(row for row in rows if row["reading_id"] == "A-S-052")["temperature_c"] = (
            7.6
        )
        path.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
        ranges_path = workspace / "evidence/secondary_ranges.json"
        ranges = json.loads(ranges_path.read_text(encoding="utf-8"))
        record = next(
            row for row in ranges["ranges"] if row["range_id"] == "RANGE-A-50-53"
        )
        selected = [
            row
            for row in rows
            if row["device_id"] == "S-A1" and 50 <= row["sequence"] <= 53
        ]
        record["readings_sha256"] = hashlib.sha256(
            (
                json.dumps(selected, sort_keys=True, separators=(",", ":")) + "\n"
            ).encode()
        ).hexdigest()
        trust = json.loads(
            (workspace / "evidence/logger_trust.json").read_text(encoding="utf-8")
        )
        payload = {
            key: value
            for key, value in record.items()
            if key not in {"key_id", "signature"}
        }
        record["signature"] = hashlib.sha256(
            (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
            + trust["verification_material"].encode()
        ).hexdigest()
        ranges_path.write_text(
            json.dumps(ranges, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        manifest_path = workspace / "policy/source_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for name in (
            "evidence/logger_readings.jsonl",
            "evidence/secondary_ranges.json",
        ):
            manifest["files"][name] = hashlib.sha256(
                (workspace / name).read_bytes()
            ).hexdigest()
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        inputs = ctl.recovery_inputs()
        plan = json.loads(
            (TASK / "tests/reference/excursion_plan.json").read_text(encoding="utf-8")
        )
        plan["source_checkpoint"] = inputs["source_checkpoint"]
        aurora = next(row for row in plan["decisions"] if row["lot_id"] == "LOT-AURORA")
        aurora.update(
            {
                "observed_max_c": 8.3,
                "out_of_range_minutes": 0,
                "disposition": "available",
                "local_mutations": [],
                "next_local_action": "none",
            }
        )
        (workspace / "excursion_plan.json").write_text(
            json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        completed = _run(workspace, "preview")
    assert completed.returncode == 0
    assert '"status": "valid"' in completed.stdout


def test_public_controller_exports_no_complete_answer_constructor() -> None:
    source = (TASK / "workspace/coldchainctl.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert not names & {
        "derive", "expected_plan", "target_plan", "reference_plan", "gold_plan"
    }
    for function in (
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    ):
        for returned in (
            node.value
            for node in ast.walk(function)
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)
        ):
            keys = {
                key.value
                for key in returned.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
            assert not keys & {"actions", "decisions", "final_rows", "plan"}
    temporary, workspace = _workspace()
    with temporary:
        ctl = _module(workspace / "coldchainctl.py", "public_coldchainctl")
        inputs = ctl.recovery_inputs()
    assert "plan" not in inputs and "decisions" not in inputs


def test_runtime_cache_and_bounded_read_only_helper_are_allowed() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        subprocess.run(["python3", "-c", "import coldchainctl"], cwd=workspace, check=True)
        (workspace / "dump_db.py").write_text("import sqlite3\n", encoding="utf-8")
        assert _score(workspace)["outcome_score"] == 1.0
        (workspace / "__pycache__").mkdir(exist_ok=True)
        (workspace / "__pycache__/payload.txt").write_text("not bytecode\n", encoding="utf-8")
        (workspace / "unknown.bin").write_bytes(b"ordinary candidate output")
        assert _score(workspace)["outcome_score"] == 1.0
        (workspace / "unsafe-link").symlink_to("excursion_plan.json")
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_source_integrity"]


def test_missing_closure_and_incomplete_state_do_not_trigger_safety_gate() -> None:
    temporary, workspace = _workspace()
    with temporary:
        shutil.copy2(
            TASK / "tests/reference/excursion_plan.json",
            workspace / "excursion_plan.json",
        )
        result = _score(workspace)
    assert 0.0 < result["outcome_score"] < 0.8
    assert result["failed_gates"] == []
    assert _check(result, "safety_and_source_integrity")["pass"] is True
    assert _check(result, "qa_packet_and_replay_closure")["pass"] is False
    assert _check(result, "interrupted_journal_and_inventory_state")["pass"] is False


def test_duplicate_plan_object_fails_the_combined_plan_and_inventory_result() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "excursion_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        plan["decisions"].append(dict(plan["decisions"][0]))
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["failed_core_cases"] == [
        "interrupted_journal_and_inventory_state"
    ]
    for case_id in (
        "aurora_excursion_resolution",
        "birch_evidence_gap_resolution",
        "cedar_unaffected_resolution",
    ):
        assert _check(result, case_id)["pass"] is True
    detail = _check(result, "interrupted_journal_and_inventory_state")["detail"]
    assert detail["duplicate_lot_ids"] is True
    assert detail["mismatched_tables"] == []


def test_protected_quantity_or_affirmative_external_flag_triggers_gate() -> None:
    temporary, workspace = _workspace(True)
    with temporary, sqlite3.connect(workspace / "state/cold_chain.db") as connection:
        connection.execute(
            "UPDATE lots SET quantity=quantity-1 WHERE lot_id='LOT-AURORA'"
        )
        connection.commit()
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_source_integrity"]

    temporary, workspace = _workspace(True)
    with temporary:
        packet_path = workspace / "state/qa_packet.json"
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        packet["external_actions_executed"] = True
        packet_path.write_text(json.dumps(packet), encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_source_integrity"]


def test_evaluator_independence_case_weights_and_semantic_builder_contract() -> None:
    source = (TASK / "tests/test_outcome.py").read_text(encoding="utf-8")
    assert "import coldchainctl" not in source
    assert "spec_from_file_location" not in source
    assert "subprocess" not in source
    cases = yaml.safe_load((TASK / "tests/cases.yaml").read_text(encoding="utf-8"))[
        "cases"
    ]
    assert sum(item["weight"] for item in cases if item.get("core")) == 0.8
    assert sum(item["weight"] for item in cases) == 1.0
    assert [item["id"] for item in cases if item.get("gate")] == [
        "safety_and_source_integrity"
    ]
    metadata = yaml.safe_load((TASK / "task.yaml").read_text(encoding="utf-8"))
    assert metadata["semantic_judge"]["case_map"] == {
        "handoff_semantics": "cold_chain_handoff"
    }
    evaluator = _module(TASK / "tests/test_outcome.py", "task131_builder")
    temporary, workspace = _workspace(True)
    with temporary:
        semantic_input = evaluator.build_semantic_judge_input(workspace)
    assert semantic_input["judge_eligible"] is True
    assert semantic_input["artifact"] == "cold_chain_handoff.md"
