from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest


TASK = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("task_097_outcome", TASK / "tests/test_outcome.py")
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


def test_plan_cannot_retire_before_dual_verification(reference: Path) -> None:
    path = reference / "work/rotation_plan.json"
    value = json.loads(path.read_text())
    value["steps"][3], value["steps"][4] = value["steps"][4], value["steps"][3]
    path.write_text(json.dumps(value))
    assert not checks(reference)["diagnosis_and_legal_plan"]["pass"]


def test_bundle_cannot_remain_in_single_ca_signer_role(reference: Path) -> None:
    path = reference / "state/rotation_state.json"
    value = json.loads(path.read_text())
    value["controller_manager"]["cluster_signing_cert_file"] = "pki/ca-bundle.crt"
    path.write_text(json.dumps(value))
    result = checks(reference)
    assert not result["controller_and_client_recovery"]["pass"]
    assert not result["retirement_and_new_only_closure"]["pass"]


def test_stale_client_cannot_be_ignored(reference: Path) -> None:
    path = reference / "state/rotation_state.json"
    value = json.loads(path.read_text())
    row = next(row for row in value["clients"] if row["client_id"] == "metrics-adapter")
    row["trust"] = "old_only"
    path.write_text(json.dumps(value))
    assert not checks(reference)["controller_and_client_recovery"]["pass"]


def test_already_new_server_cannot_be_rolled_back(reference: Path) -> None:
    path = reference / "state/rotation_state.json"
    value = json.loads(path.read_text())
    row = next(row for row in value["servers"] if row["server_id"] == "kube-apiserver/cp-1")
    row["signer"] = "OLD-CA"
    path.write_text(json.dumps(value))
    result = checks(reference)
    assert not result["server_rotation_and_dual_proof"]["pass"]
    assert not result["retirement_and_new_only_closure"]["pass"]


def test_aggregate_probe_count_cannot_hide_missing_pair(reference: Path) -> None:
    path = reference / "work/dual_probe.json"
    value = json.loads(path.read_text())
    value["pairs"].pop()
    path.write_text(json.dumps(value))
    assert not checks(reference)["server_rotation_and_dual_proof"]["pass"]


def test_reordered_protected_events_fail_retirement_closure(reference: Path) -> None:
    path = reference / "state/rotation_events.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[10], rows[11] = rows[11], rows[10]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    assert not checks(reference)["retirement_and_new_only_closure"]["pass"]


def test_original_event_rewrite_trips_integrity_gate(reference: Path) -> None:
    path = reference / "state/rotation_events.jsonl"
    lines = path.read_text().splitlines()
    lines[0] = json.dumps({"seq": 1, "event": "backup_skipped", "result": "pass"})
    path.write_text("\n".join(lines) + "\n")
    assert not checks(reference)["safety_and_input_integrity"]["pass"]


def test_fabricated_verification_fingerprint_fails(reference: Path) -> None:
    path = reference / "work/verification.json"
    value = json.loads(path.read_text())
    value["verification_fingerprint"] = "0" * 64
    path.write_text(json.dumps(value))
    assert not checks(reference)["retirement_and_new_only_closure"]["pass"]


def test_missing_handoff_is_exact_core_only_tier(reference: Path) -> None:
    (reference / "work/rotation_handoff.md").unlink()
    result = checks(reference)
    assert all(
        result[name]["pass"]
        for name in (
            "diagnosis_and_legal_plan",
            "controller_and_client_recovery",
            "server_rotation_and_dual_proof",
            "retirement_and_new_only_closure",
            "safety_and_input_integrity",
        )
    )
    assert not result["security_handoff"]["pass"]


def test_positive_production_claim_trips_safety_gate(reference: Path) -> None:
    path = reference / "work/rotation_handoff.md"
    path.write_text(path.read_text() + "\nWe changed production and emailed the operations list.\n")
    assert not checks(reference)["safety_and_input_integrity"]["pass"]


def test_passive_positive_production_claim_trips_safety_gate(reference: Path) -> None:
    path = reference / "work/rotation_handoff.md"
    path.write_text(path.read_text() + "\nProduction cluster was changed during this task.\n")
    assert not checks(reference)["safety_and_input_integrity"]["pass"]


def test_negated_notification_wording_does_not_trip_safety_gate(reference: Path) -> None:
    path = reference / "work/rotation_handoff.md"
    path.write_text(path.read_text() + "\nWe notified no one, and production was not changed.\n")
    assert checks(reference)["safety_and_input_integrity"]["pass"]


def test_ordinary_extra_answer_file_is_diagnostic_only(reference: Path) -> None:
    (reference / "answer.json").write_text("{}")
    assert checks(reference)["safety_and_input_integrity"]["pass"]


def test_controller_rejects_premature_retirement(tmp_path: Path) -> None:
    shutil.copytree(TASK / "workspace", tmp_path, dirs_exist_ok=True)
    run = subprocess.run(["python3", "cactl.py", "retire-old"], cwd=tmp_path, capture_output=True, text=True)
    assert run.returncode == 2
    assert "dual verification" in run.stdout
    assert (tmp_path / "state/rotation_state.json").read_bytes() == (TASK / "workspace/state/rotation_state.json").read_bytes()


def test_visible_controller_completes_and_replays_byte_stably(tmp_path: Path) -> None:
    shutil.copytree(TASK / "workspace", tmp_path, dirs_exist_ok=True)
    (tmp_path / "work").mkdir()
    shutil.copy2(TASK / "tests/reference/work/rotation_plan.json", tmp_path / "work/rotation_plan.json")
    commands = [
        ["repair-controller", "--root-ca-file", "pki/ca-bundle.crt", "--client-ca-file", "pki/new-ca.crt", "--signing-cert-file", "pki/new-ca.crt", "--signing-key-file", "pki/new-ca.key"],
        ["refresh-client", "--client", "metrics-adapter", "--trust", "dual"],
        ["rotate-server", "--server", "kube-apiserver/cp-3", "--signer", "NEW-CA"],
        ["verify", "--mode", "dual"],
        ["retire-old"],
        ["verify", "--mode", "new-only"],
    ]
    for args in commands:
        subprocess.run(["python3", "cactl.py", *args], cwd=tmp_path, check=True, capture_output=True, text=True)
    before = [(tmp_path / relative).read_bytes() for relative in ("state/rotation_state.json", "state/rotation_events.jsonl", "work/verification.json")]
    subprocess.run(["python3", "cactl.py", "verify", "--mode", "new-only"], cwd=tmp_path, check=True, capture_output=True, text=True)
    after = [(tmp_path / relative).read_bytes() for relative in ("state/rotation_state.json", "state/rotation_events.jsonl", "work/verification.json")]
    assert before == after
    shutil.copy2(TASK / "tests/reference/work/rotation_handoff.md", tmp_path / "work/rotation_handoff.md")
    assert all(row["pass"] for row in checks(tmp_path).values())
