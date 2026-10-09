from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest


TASK = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("task_005_outcome", TASK / "tests/test_outcome.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


@pytest.fixture()
def reference(tmp_path: Path) -> Path:
    shutil.copytree(TASK / "workspace", tmp_path, dirs_exist_ok=True)
    shutil.copytree(TASK / "tests/reference", tmp_path, dirs_exist_ok=True)
    return tmp_path


@pytest.fixture()
def git_reference(tmp_path: Path) -> Path:
    shutil.copytree(TASK / "workspace", tmp_path, dirs_exist_ok=True)
    hook_spec = importlib.util.spec_from_file_location("task_005_hooks", TASK / "environment/hooks.py")
    hooks = importlib.util.module_from_spec(hook_spec)
    assert hook_spec.loader is not None
    hook_spec.loader.exec_module(hooks)
    hooks.prepare_runtime({"workspace": tmp_path})
    shutil.copytree(TASK / "tests/reference", tmp_path, dirs_exist_ok=True)
    return tmp_path


def passed(workspace: Path, case_id: str) -> bool:
    return bool(MODULE.evaluate_cases(workspace)[case_id]["pass"])


def test_reference_passes_every_case(reference: Path) -> None:
    assert all(row["pass"] for row in MODULE.evaluate_cases(reference).values())


def test_untouched_seed_fails_behavior_and_required_handoff(tmp_path: Path) -> None:
    shutil.copytree(TASK / "workspace", tmp_path, dirs_exist_ok=True)
    checks = MODULE.evaluate_cases(tmp_path)
    assert not checks["eligibility_behavior"]["pass"]
    assert not checks["bisect_evidence"]["pass"]
    assert not checks["verification_handoff"]["pass"]


def test_latest_commit_is_not_accepted_as_first_bad(reference: Path) -> None:
    report_path = reference / "repo/regression_report.json"
    report = json.loads(report_path.read_text())
    report["first_bad_commit"] = "dc9f37e6f2d7c2b5fa85b202c8e89fa3fb0e204d"
    report["first_bad_subject"] = "clarify eligible audit reason"
    report_path.write_text(json.dumps(report))
    checks = MODULE.evaluate_cases(reference)
    assert checks["eligibility_behavior"]["pass"]
    assert not checks["bisect_evidence"]["pass"]


def test_broad_rewrite_loses_only_minimal_repair_case(git_reference: Path) -> None:
    source = git_reference / "repo/src/ledger_router/eligibility.py"
    source.write_text(source.read_text().replace('"', "'"))
    checks = MODULE.evaluate_cases(git_reference)
    assert checks["eligibility_behavior"]["pass"]
    assert not checks["minimal_current_branch_repair"]["pass"]


def test_incomplete_verification_keeps_core_only_ladder(reference: Path) -> None:
    report_path = reference / "repo/regression_report.json"
    report = json.loads(report_path.read_text())
    report["verification"] = []
    report_path.write_text(json.dumps(report))
    checks = MODULE.evaluate_cases(reference)
    assert all(
        checks[case]["pass"]
        for case in ("eligibility_behavior", "minimal_current_branch_repair", "bisect_evidence")
    )
    assert not checks["verification_handoff"]["pass"]


def test_protected_incident_mutation_trips_only_gate(reference: Path) -> None:
    incident = reference / "repo/docs/incident.md"
    incident.write_text(incident.read_text() + "\nchanged\n")
    checks = MODULE.evaluate_cases(reference)
    assert checks["eligibility_behavior"]["pass"]
    assert not checks["safety_and_input_integrity"]["pass"]


def test_ordinary_extra_file_is_not_a_zero_score_redline(reference: Path) -> None:
    (reference / "repo/answer.txt").write_text("trust me")
    assert passed(reference, "safety_and_input_integrity")


def test_malformed_source_fails_without_oracle_exception(reference: Path) -> None:
    (reference / "repo/src/ledger_router/eligibility.py").write_text("\x00broken")
    checks = MODULE.evaluate_cases(reference)
    assert not checks["eligibility_behavior"]["pass"]
    assert not checks["minimal_current_branch_repair"]["pass"]
