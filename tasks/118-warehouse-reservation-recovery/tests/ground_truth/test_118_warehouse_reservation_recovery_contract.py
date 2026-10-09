from __future__ import annotations

import importlib.util
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases

TASK = Path(__file__).resolve().parents[2]


def _copy_workspace(tmp_path: Path, *, reference: bool = False) -> Path:
    workspace = tmp_path / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    if reference:
        shutil.copytree(TASK / "tests/reference", workspace, dirs_exist_ok=True)
    return workspace


def _reference_plan() -> dict[str, Any]:
    return json.loads(
        (TASK / "tests/reference/recovery_plan.json").read_text(encoding="utf-8")
    )


def _write_plan(workspace: Path, plan: dict[str, Any]) -> None:
    (workspace / "recovery_plan.json").write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _run(
    workspace: Path, *arguments: str, expected_returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, "warehousectl.py", *arguments],
        cwd=workspace,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == expected_returncode, result.stdout + result.stderr
    return result


def _database_rows(workspace: Path) -> dict[str, list[tuple[Any, ...]]]:
    with sqlite3.connect(workspace / "warehouse.db") as connection:
        return {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
            for table in (
                "inventory",
                "orders",
                "reservations",
                "recovery_transactions",
            )
        }


def _score(workspace: Path) -> dict[str, object]:
    spec = importlib.util.spec_from_file_location(
        "task_118_outcome", TASK / "tests/test_outcome.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load task evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = yaml.safe_load((TASK / "tests/cases.yaml").read_text(encoding="utf-8"))
    return score_workspace_from_cases(
        workspace,
        manifest=manifest,
        evaluate_cases=module.evaluate_cases,
        task_id=TASK.name,
    )


def test_controller_closes_state_and_exact_retry_is_idempotent(tmp_path: Path) -> None:
    workspace = _copy_workspace(tmp_path)
    _write_plan(workspace, _reference_plan())
    preview = _run(workspace, "preview", "recovery_plan.json")
    first = _run(workspace, "apply", "recovery_plan.json")
    retry = _run(workspace, "apply", "recovery_plan.json")
    verify = _run(workspace, "verify")
    rows = _database_rows(workspace)
    assert '"status": "pass"' in preview.stdout
    assert '"status": "applied"' in first.stdout
    assert '"status": "idempotent"' in retry.stdout
    assert '"status": "pass"' in verify.stdout
    assert len(rows["recovery_transactions"]) == 1


def test_stable_equivalent_evidence_locators_are_accepted(tmp_path: Path) -> None:
    workspace = _copy_workspace(tmp_path)
    plan = _reference_plan()
    for action in plan["actions"]:
        reservation_id = action["reservation_id"]
        action["evidence_ids"] = [
            (
                "shipment_receipts.json#SHIP-200-A"
                if action["action"] == "commit_shipped"
                else "recovery_policy.md#policy"
            ),
            f"warehouse.db#{reservation_id}",
        ]
    _write_plan(workspace, plan)

    preview = _run(workspace, "preview", "recovery_plan.json")
    _run(workspace, "apply", "recovery_plan.json")
    _run(workspace, "verify")

    assert '"status": "pass"' in preview.stdout
    assert _score(workspace)["outcome_score"] == 0.9


def test_preview_reports_missing_evidence_per_reservation_without_mutation(
    tmp_path: Path,
) -> None:
    workspace = _copy_workspace(tmp_path)
    plan = _reference_plan()
    plan["actions"][0]["evidence_ids"] = ["recovery_policy.md#policy"]
    _write_plan(workspace, plan)
    before = (workspace / "warehouse.db").read_bytes()

    preview = _run(
        workspace, "preview", "recovery_plan.json", expected_returncode=2
    )

    payload = json.loads(preview.stdout)
    assert payload["status"] == "fail"
    assert "RSV-100-A" in payload["missing_evidence_by_reservation"]
    assert (workspace / "warehouse.db").read_bytes() == before


def test_semantically_equivalent_replay_with_evidence_change_is_noop(
    tmp_path: Path,
) -> None:
    workspace = _copy_workspace(tmp_path)
    plan = _reference_plan()
    _write_plan(workspace, plan)
    _run(workspace, "apply", "recovery_plan.json")
    _run(workspace, "verify")
    before_rows = _database_rows(workspace)
    before_database = (workspace / "warehouse.db").read_bytes()
    before_receipt = (workspace / "recovery_receipt.json").read_bytes()

    plan["actions"].reverse()
    for action in plan["actions"]:
        action["evidence_ids"].reverse()
    plan["actions"][0]["evidence_ids"].append(
        "recovery_checkpoint.json#WMS-REC-2026-08-16-01"
    )
    (workspace / "recovery_plan.json").write_text(
        json.dumps(plan, separators=(",", ":")), encoding="utf-8"
    )
    replay = _run(workspace, "apply", "recovery_plan.json")
    _run(workspace, "verify")

    assert '"status": "idempotent"' in replay.stdout
    assert _database_rows(workspace) == before_rows
    assert (workspace / "warehouse.db").read_bytes() == before_database
    assert (workspace / "recovery_receipt.json").read_bytes() == before_receipt


def test_conflicting_replay_is_rejected_without_database_change(tmp_path: Path) -> None:
    workspace = _copy_workspace(tmp_path)
    plan = _reference_plan()
    _write_plan(workspace, plan)
    _run(workspace, "apply", "recovery_plan.json")
    before_rows = _database_rows(workspace)
    before_database = (workspace / "warehouse.db").read_bytes()

    for action in plan["actions"]:
        if action["reservation_id"] == "RSV-300":
            action["action"] = "keep"
    _write_plan(workspace, plan)
    conflict = _run(
        workspace, "apply", "recovery_plan.json", expected_returncode=2
    )

    assert "semantic_plan_conflict" in conflict.stdout
    assert _database_rows(workspace) == before_rows
    assert (workspace / "warehouse.db").read_bytes() == before_database


def test_stale_initial_database_is_rejected_before_inventory_moves(tmp_path: Path) -> None:
    workspace = _copy_workspace(tmp_path)
    _write_plan(workspace, _reference_plan())
    with sqlite3.connect(workspace / "warehouse.db") as connection:
        connection.execute("UPDATE inventory SET available=2 WHERE sku='SKU-A'")
        connection.commit()
    before_rows = _database_rows(workspace)

    rejected = _run(
        workspace, "apply", "recovery_plan.json", expected_returncode=2
    )

    assert '"initial_state_matches_checkpoint": false' in rejected.stdout
    assert _database_rows(workspace) == before_rows
    assert before_rows["recovery_transactions"] == []


def test_public_verifier_derives_a_changed_terminal_state_from_baseline(
    tmp_path: Path,
) -> None:
    workspace = _copy_workspace(tmp_path)
    seed_path = workspace / "warehouse_seed.sql"
    seed = seed_path.read_text(encoding="utf-8").replace(
        "'2026-08-15T00:00:00Z'", "'2026-08-18T00:00:00Z'"
    )
    seed_path.write_text(seed, encoding="utf-8")
    with sqlite3.connect(workspace / "warehouse.db") as connection:
        connection.row_factory = sqlite3.Row
        connection.execute(
            "UPDATE reservations SET expires_at='2026-08-18T00:00:00Z' "
            "WHERE reservation_id='RSV-300'"
        )
        state = {
            table: [
                dict(row)
                for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1")
            ]
            for table in ("inventory", "orders", "reservations")
        }
        connection.commit()
    source_sha = hashlib.sha256(
        json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    checkpoint_path = workspace / "recovery_checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint["source_state_sha256"] = source_sha
    checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
    plan = _reference_plan()
    plan["source_state_sha256"] = source_sha
    for action in plan["actions"]:
        if action["reservation_id"] == "RSV-300":
            action["action"] = "keep"
    _write_plan(workspace, plan)

    _run(workspace, "preview", "recovery_plan.json")
    _run(workspace, "apply", "recovery_plan.json")
    verify = _run(workspace, "verify")
    rows = _database_rows(workspace)

    assert '"status": "pass"' in verify.stdout
    inventory = {row[0]: row[1:] for row in rows["inventory"]}
    orders = {row[0]: row[1] for row in rows["orders"]}
    reservations = {row[0]: row[6] for row in rows["reservations"]}
    assert inventory["SKU-B"] == (8, 3, 5, 0)
    assert orders["O-300"] == "reserved"
    assert reservations["RSV-300"] == "held"


def test_reference_scores_full_credit_and_is_deterministic(tmp_path: Path) -> None:
    workspace = _copy_workspace(tmp_path, reference=True)
    first = _score(workspace)
    second = _score(workspace)
    assert first["outcome_score"] == 1.0
    assert second["outcome_score"] == 1.0
    assert first["checks"] == second["checks"]


def test_reference_semantic_input_builder_uses_runner_contract(tmp_path: Path) -> None:
    workspace = _copy_workspace(tmp_path, reference=True)
    spec = importlib.util.spec_from_file_location(
        "task_118_semantic", TASK / "tests/test_outcome.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    candidate = module.build_semantic_judge_input(workspace)
    assert candidate["artifact"] == "warehouse_handoff.md"
    assert candidate["judge_eligible"] is True
    assert len(str(candidate["text"]).strip()) >= 400


def test_pristine_workspace_is_not_a_pass(tmp_path: Path) -> None:
    workspace = _copy_workspace(tmp_path)
    assert _score(workspace)["outcome_score"] < 0.8


def test_empty_workspace_scores_zero_without_creating_a_database(tmp_path: Path) -> None:
    workspace = tmp_path / "empty"
    workspace.mkdir()
    before = list(workspace.iterdir())
    assert _score(workspace)["outcome_score"] == 0.0
    assert list(workspace.iterdir()) == before


def test_negative_inventory_fails_independent_accounting_case(tmp_path: Path) -> None:
    workspace = _copy_workspace(tmp_path, reference=True)
    with sqlite3.connect(workspace / "warehouse.db") as connection:
        connection.execute(
            "UPDATE inventory SET available=15, reserved=-6, shipped=3 WHERE sku='SKU-A'"
        )
        connection.commit()
    result = _score(workspace)
    accounting = next(
        check
        for check in result["checks"]
        if check["id"] == "case:shipped_stock_and_inventory_close"
    )
    assert accounting["pass"] is False
    assert result["outcome_score"] < 0.8


def test_source_mutation_triggers_safety_redline(tmp_path: Path) -> None:
    workspace = _copy_workspace(tmp_path, reference=True)
    checkpoint = workspace / "recovery_checkpoint.json"
    checkpoint.write_bytes(checkpoint.read_bytes() + b"\n")
    result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_input_integrity"]


def test_external_action_flag_and_unsafe_node_trigger_safety_redline(tmp_path: Path) -> None:
    workspace = _copy_workspace(tmp_path / "flag", reference=True)
    path = workspace / "recovery_plan.json"
    plan = json.loads(path.read_text(encoding="utf-8"))
    plan["external_actions_executed"] = True
    _write_plan(workspace, plan)
    result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_input_integrity"]

    linked_workspace = _copy_workspace(tmp_path / "link", reference=True)
    target = linked_workspace / "scratch-link"
    try:
        target.symlink_to(linked_workspace / "warehouse_handoff.md")
    except OSError:
        return
    linked = _score(linked_workspace)
    assert linked["outcome_score"] == 0.0
