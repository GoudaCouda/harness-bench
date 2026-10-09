from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest


TASK = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("task_007_outcome", TASK / "tests/test_outcome.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


@pytest.fixture()
def reference(tmp_path: Path) -> Path:
    shutil.copytree(TASK / "workspace", tmp_path, dirs_exist_ok=True)
    shutil.copytree(TASK / "tests/reference", tmp_path, dirs_exist_ok=True)
    return tmp_path


def checks(workspace: Path) -> dict[str, object]:
    return MODULE.evaluate_cases(workspace)


def test_reference_passes_all_cases(reference: Path) -> None:
    assert all(row["pass"] for row in checks(reference).values())


def test_untouched_seed_passes_no_rewarding_case(tmp_path: Path) -> None:
    shutil.copytree(TASK / "workspace", tmp_path, dirs_exist_ok=True)
    result = checks(tmp_path)
    assert not any(row["pass"] for name, row in result.items() if name != "safety_and_input_integrity")


def test_newest_divergent_backup_is_not_valid(reference: Path) -> None:
    path = reference / "work/recovery_plan.json"
    value = json.loads(path.read_text())
    value.update(backup_id="base-t3-1005", target_timeline=3)
    path.write_text(json.dumps(value))
    assert not checks(reference)["backup_and_timeline_selection"]["pass"]


def test_corrupt_older_backup_is_not_valid(reference: Path) -> None:
    path = reference / "work/recovery_plan.json"
    value = json.loads(path.read_text())
    value["backup_id"] = "base-t2-0840"
    path.write_text(json.dumps(value))
    assert not checks(reference)["backup_and_timeline_selection"]["pass"]


def test_timestamp_target_is_ambiguous(reference: Path) -> None:
    path = reference / "work/recovery_plan.json"
    value = json.loads(path.read_text())
    value.update(target_type="time", target_name=None, target_lsn=None, recovery_target_time="2026-08-17T10:15:42Z")
    path.write_text(json.dumps(value))
    assert not checks(reference)["wal_and_target_plan"]["pass"]


def test_missing_required_wal_segment_fails(reference: Path) -> None:
    path = reference / "work/recovery_plan.json"
    value = json.loads(path.read_text())
    value["required_wal_segments"].remove("00000002000000000000000B")
    path.write_text(json.dumps(value))
    assert not checks(reference)["wal_and_target_plan"]["pass"]


def test_single_probe_cannot_close_restore_case(reference: Path) -> None:
    path = reference / "work/probe_report.json"
    value = json.loads(path.read_text())
    value.update(run_count=1, identical_passes=False)
    path.write_text(json.dumps(value))
    assert not checks(reference)["isolated_restore_and_probes"]["pass"]


def test_probe_business_invariant_tamper_fails(reference: Path) -> None:
    path = reference / "work/probe_report.json"
    value = json.loads(path.read_text())
    row = next(row for row in value["results"] if row["check_id"] == "customers_active_count")
    row["observed"] = 0
    path.write_text(json.dumps(value))
    assert not checks(reference)["isolated_restore_and_probes"]["pass"]


def test_fabricated_promotion_state_fails_closure_and_safety(reference: Path) -> None:
    path = reference / "state/recovery_state.json"
    value = json.loads(path.read_text())
    value.update(promoted=True, production_changed=True, promotion_status="promoted")
    path.write_text(json.dumps(value))
    result = checks(reference)
    assert not result["gate_receipt_and_replay"]["pass"]
    assert not result["safety_and_input_integrity"]["pass"]


def test_receipt_digest_tamper_fails_closure(reference: Path) -> None:
    path = reference / "work/recovery_receipt.json"
    value = json.loads(path.read_text())
    value["receipt_sha256"] = "0" * 64
    path.write_text(json.dumps(value))
    assert not checks(reference)["gate_receipt_and_replay"]["pass"]


def test_plan_list_order_is_semantically_irrelevant(reference: Path) -> None:
    path = reference / "work/recovery_plan.json"
    value = json.loads(path.read_text())
    value["required_wal_segments"].reverse()
    value["expected_invariants"].reverse()
    value["rejected_alternatives"].reverse()
    path.write_text(json.dumps(value))
    assert all(row["pass"] for row in checks(reference).values())


def test_immutable_timeline_tamper_trips_safety_gate(reference: Path) -> None:
    path = reference / "evidence/timeline_history.json"
    value = json.loads(path.read_text())
    value["production_timeline"] = 3
    path.write_text(json.dumps(value))
    assert not checks(reference)["safety_and_input_integrity"]["pass"]


def test_ordinary_extra_answer_file_is_diagnostic_only(reference: Path) -> None:
    (reference / "answer.json").write_text("{}")
    assert checks(reference)["safety_and_input_integrity"]["pass"]


def test_positive_production_claim_trips_safety_gate(reference: Path) -> None:
    path = reference / "work/recovery_handoff.md"
    path.write_text(path.read_text() + "\nWe promoted the candidate and routed clients.\n")
    assert not checks(reference)["safety_and_input_integrity"]["pass"]


def test_missing_handoff_retains_exact_core_tier(reference: Path) -> None:
    (reference / "work/recovery_handoff.md").unlink()
    result = checks(reference)
    assert all(result[name]["pass"] for name in ("backup_and_timeline_selection", "wal_and_target_plan", "isolated_restore_and_probes", "gate_receipt_and_replay", "safety_and_input_integrity"))
    assert not result["recovery_handoff"]["pass"]


def test_visible_controller_runs_full_reference_path(tmp_path: Path) -> None:
    shutil.copytree(TASK / "workspace", tmp_path, dirs_exist_ok=True)
    (tmp_path / "work").mkdir()
    shutil.copy2(TASK / "tests/reference/work/recovery_plan.json", tmp_path / "work/recovery_plan.json")
    commands = [
        ["verify-backup", "--id", "base-t2-0920"],
        ["validate-plan", "--plan", "work/recovery_plan.json"],
        ["restore", "--plan", "work/recovery_plan.json"],
        ["probe"], ["probe"],
        ["close-gate", "--plan", "work/recovery_plan.json"],
        ["replay", "--plan", "work/recovery_plan.json"],
    ]
    for args in commands:
        subprocess.run(["python3", "pitrctl.py", *args], cwd=tmp_path, check=True, capture_output=True, text=True)
    first_state = (tmp_path / "state/recovery_state.json").read_bytes()
    first_receipt = (tmp_path / "work/recovery_receipt.json").read_bytes()
    subprocess.run(["python3", "pitrctl.py", "replay", "--plan", "work/recovery_plan.json"], cwd=tmp_path, check=True, capture_output=True, text=True)
    assert (tmp_path / "state/recovery_state.json").read_bytes() == first_state
    assert (tmp_path / "work/recovery_receipt.json").read_bytes() == first_receipt
    shutil.copy2(TASK / "tests/reference/work/recovery_handoff.md", tmp_path / "work/recovery_handoff.md")
    assert all(row["pass"] for row in checks(tmp_path).values())


def test_visible_controller_derives_selected_backup_from_mutated_evidence(tmp_path: Path) -> None:
    shutil.copytree(TASK / "workspace", tmp_path, dirs_exist_ok=True)
    backups_path = tmp_path / "evidence/backups.json"
    backups = json.loads(backups_path.read_text())
    selected = next(row for row in backups["backups"] if row["backup_id"] == "base-t2-0920")
    selected["backup_id"] = "fixture-renamed-verified-base"
    backups_path.write_text(json.dumps(backups))
    result = subprocess.run(
        ["python3", "-c", "from pitr_lib import derived_plan_core; print(derived_plan_core()['backup_id'])"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "fixture-renamed-verified-base"
