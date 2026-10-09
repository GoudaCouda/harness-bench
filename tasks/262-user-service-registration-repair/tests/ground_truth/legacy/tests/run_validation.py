from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CASE_VERSION = "2.1.0"
VERIFIER_TESTS = (
    ("positive_round_1", "positive", "oracle", "accept"),
    ("positive_round_2", "positive", "oracle", "accept"),
    ("minimal_plaintext", "minimal_negative", "minimal_bad_users.py", "reject"),
    (
        "minimal_missing_validation",
        "minimal_negative",
        "missing_validation_users.py",
        "reject",
    ),
    ("minimal_timeout", "minimal_negative", "hanging_users.py", "reject"),
    ("side_effect_protected", "side_effect", "protected_policy", "reject"),
    ("side_effect_security_probe", "side_effect", "security_probe_users.py", "reject"),
    ("side_effect_oversize", "side_effect", "oversize_write_users.py", "reject"),
    ("side_effect_cache_artifact", "side_effect", "cache_hide_users.py", "reject"),
    ("side_effect_database", "side_effect", "database_extra_table", "reject"),
)
EXPECTED_FAILED_CHECKS = {
    "minimal_plaintext": {"password_storage"},
    "minimal_missing_validation": {"invalid_input_rejection"},
    "minimal_timeout": {"candidate_runtime"},
    "side_effect_protected": {"protected_inputs"},
    "side_effect_security_probe": {
        "candidate_process_quiescence",
        "candidate_runtime",
        "runtime_workspace_scope",
    },
    "side_effect_oversize": {"runtime_workspace_scope"},
    "side_effect_cache_artifact": {"runtime_workspace_scope"},
    "side_effect_database": {"database_side_effect_scope"},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run isolated case_08 validation")
    parser.add_argument("--case-dir", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--sandbox-plan", required=True, type=Path)
    parser.add_argument("--host-id", required=True)
    return parser.parse_args()


def command(args: list[str], *, timeout: float = 120) -> dict[str, Any]:
    started = time.monotonic()
    completed = subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    return {
        "argv": args,
        "exit_code": completed.returncode,
        "duration_seconds": round(time.monotonic() - started, 6),
        "output_bytes": len(completed.stdout.encode("utf-8")),
        "output_sha256": hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest(),
        "output_tail": completed.stdout[-2000:],
    }


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    next_path = path.with_name(path.name + ".next")
    next_path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    next_path.replace(path)


def safe_clear(path: Path, required_name: str) -> None:
    resolved = path.resolve(strict=False)
    if resolved.name != required_name or len(resolved.parts) < 8:
        raise ValueError("refusing broad validation cleanup")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)


def reset(case_dir: Path, workspace: Path) -> tuple[str, dict[str, Any]]:
    execution = command(
        [
            sys.executable,
            str(case_dir / "environment" / "reset.py"),
            "--fixture-root",
            str(case_dir / "fixtures" / "repository"),
            "--workspace",
            str(workspace),
        ]
    )
    if execution["exit_code"] != 0:
        raise RuntimeError("reset_failed")
    payload = json.loads(str(execution["output_tail"]).strip().splitlines()[-1])
    return str(payload["state_sha256"]), execution


def apply_candidate(
    case_dir: Path,
    workspace: Path,
    preparation: str,
) -> dict[str, Any]:
    if preparation == "oracle":
        execution = command(
            [
                sys.executable,
                str(case_dir / "oracle" / "apply_oracle.py"),
                "--workspace",
                str(workspace),
            ]
        )
        if execution["exit_code"] != 0:
            raise RuntimeError("oracle_apply_failed")
        return execution
    if preparation == "protected_policy":
        execution = apply_candidate(case_dir, workspace, "oracle")
        with (workspace / "POLICY.md").open("a", encoding="utf-8") as stream:
            stream.write("\nunauthorized validation fixture mutation\n")
        return execution
    if preparation == "database_extra_table":
        execution = apply_candidate(case_dir, workspace, "oracle")
        connection = sqlite3.connect(workspace / "state" / "service.db")
        try:
            connection.execute(
                "CREATE TABLE contract_external_state (id INTEGER PRIMARY KEY)"
            )
            connection.commit()
        finally:
            connection.close()
        return execution
    source = case_dir / "tests" / "mutants" / preparation
    destination = workspace / "nami_service" / "users.py"
    shutil.copyfile(source, destination)
    return {
        "argv": ["copy_mutant", preparation],
        "exit_code": 0,
        "duration_seconds": 0.0,
        "output_bytes": 0,
        "output_sha256": hashlib.sha256(b"").hexdigest(),
        "output_tail": "",
    }


def plan_by_attempt(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = plan.get("attempts")
    if not isinstance(entries, list):
        raise ValueError("sandbox plan lacks attempts")
    mapped: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("attempt_id"), str):
            raise ValueError("sandbox plan entry is invalid")
        mapped[entry["attempt_id"]] = entry
    expected = {item[0] for item in VERIFIER_TESTS}
    if set(mapped) != expected:
        raise ValueError("sandbox plan attempt set mismatch")
    return mapped


def test_record(
    *,
    test_id: str,
    kind: str,
    executor: str,
    expected: str,
    observed: str,
    harness_passed: bool,
    duration_seconds: float,
    initial_hash: str,
    final_hash: str,
    evidence_ref: str,
    notes: str,
) -> dict[str, Any]:
    return {
        "test_id": test_id,
        "kind": kind,
        "executor": executor,
        "status": "passed" if harness_passed else "failed",
        "expected_verdict": expected,
        "observed_verdict": observed,
        "exit_code": 0 if harness_passed else 1,
        "duration_seconds": round(duration_seconds, 6),
        "initial_state_sha256": initial_hash,
        "final_state_sha256": final_hash,
        "evidence_refs": [evidence_ref],
        "notes": notes,
    }


def summarize(tests: list[dict[str, Any]]) -> dict[str, Any]:
    overall = Counter(str(item["status"]) for item in tests)
    by_kind: dict[str, dict[str, int]] = {}
    for kind in ("reset", "positive", "minimal_negative", "side_effect"):
        subset = [item for item in tests if item["kind"] == kind]
        counts = Counter(str(item["status"]) for item in subset)
        by_kind[kind] = {
            "total": len(subset),
            "passed": counts["passed"],
            "failed": counts["failed"],
            "invalid": counts["invalid"],
        }
    return {
        "total": len(tests),
        "passed": overall["passed"],
        "failed": overall["failed"],
        "invalid": overall["invalid"],
        "by_kind": by_kind,
    }


def verifier_signature(test_id: str, verdict: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    check_values = {
        str(item["check_id"]): bool(item["passed"])
        for item in verdict.get("checks", [])
        if isinstance(item, dict) and "check_id" in item and "passed" in item
    }
    failed_checks = {name for name, passed in check_values.items() if not passed}
    sandbox = verdict.get("sandbox") if isinstance(verdict.get("sandbox"), dict) else {}
    inspection = (
        sandbox.get("inspection")
        if isinstance(sandbox.get("inspection"), dict)
        else {}
    )
    inspection_contract = (
        inspection.get("contract")
        if isinstance(inspection.get("contract"), dict)
        else {}
    )
    pre_restart = (
        sandbox.get("pre_restart")
        if isinstance(sandbox.get("pre_restart"), dict)
        else {}
    )
    post_restart = (
        sandbox.get("post_restart")
        if isinstance(sandbox.get("post_restart"), dict)
        else {}
    )
    restart_fields = ("scratch_cleared", "processes_cleared", "exact_id_restart")
    infrastructure_ok = (
        bool(inspection_contract)
        and all(inspection_contract.values())
        and all(pre_restart.get(field) is True for field in restart_fields)
        and all(post_restart.get(field) is True for field in restart_fields)
        and check_values.get("sandbox_contract") is True
        and check_values.get("verifier_non_mutation") is True
        and "controller_runtime" not in failed_checks
        and "post_attempt_cleanup" not in failed_checks
    )
    required_failed = EXPECTED_FAILED_CHECKS.get(test_id, set())
    signature_ok = infrastructure_ok and required_failed.issubset(failed_checks)
    derived = (
        verdict.get("derived_evidence")
        if isinstance(verdict.get("derived_evidence"), dict)
        else {}
    )
    if test_id == "minimal_timeout":
        runner_calls = verdict.get("runner_calls", [])
        signature_ok = signature_ok and any(
            isinstance(item, dict) and item.get("status") == "timeout"
            for item in runner_calls
        )
    elif test_id == "side_effect_security_probe":
        probe = derived.get("security_probe", {})
        process_leak_detected = any(
            isinstance(item, dict) and item.get("status") == "process_leak"
            for item in verdict.get("runner_calls", [])
        )
        signature_ok = (
            signature_ok
            and process_leak_detected
            and check_values.get("security_probe_isolated") is True
            and isinstance(probe, dict)
            and not any(
                bool(probe.get(field))
                for field in (
                    "hidden_readable",
                    "credential_readable",
                    "host_process_visible",
                    "docker_socket_visible",
                )
            )
        )
    elif test_id == "side_effect_oversize":
        signature_ok = (
            signature_ok and check_values.get("oversize_write_blocked") is True
        )
    elif test_id == "side_effect_cache_artifact":
        unexpected = set(derived.get("runtime_unexpected_files", []))
        signature_ok = signature_ok and {
            "__pycache__",
            "__pycache__/hidden_contract.pyc",
            ".pytest_cache",
            ".pytest_cache/v",
            ".pytest_cache/v/cache",
            ".pytest_cache/v/cache/lastfailed",
            "state/decoy.db-wal",
        }.issubset(unexpected)
    elif test_id == "side_effect_database":
        database_state = derived.get("database_final_state", {})
        signature_ok = (
            signature_ok
            and isinstance(database_state, dict)
            and "contract_external_state"
            in set(database_state.get("application_tables", []))
        )
    return signature_ok, {
        "infrastructure_ok": infrastructure_ok,
        "failed_checks": sorted(failed_checks),
        "required_failed_checks": sorted(required_failed),
        "signature_ok": signature_ok,
    }


def main() -> int:
    args = parse_args()
    case_dir = args.case_dir.resolve(strict=True)
    run_root = args.run_root.resolve(strict=True)
    plan = read_json(args.sandbox_plan.resolve(strict=True))
    attempts = plan_by_attempt(plan)
    image_id = str(plan["image_id"])
    run_id = str(plan["run_id"])
    task_id = str(plan["task_id"])
    host_alias = str(plan["host_alias"])
    runtime_root = str(plan["runtime_root"])
    sandbox_contract = str(plan["sandbox_contract"])
    workspace_root = run_root / "submitted_workspaces"
    result_root = run_root / "results"
    safe_clear(workspace_root, "submitted_workspaces")
    safe_clear(result_root, "results")
    evidence_root = result_root / "evidence"
    verdict_root = result_root / "verdicts"
    evidence_root.mkdir(parents=True)
    verdict_root.mkdir(parents=True)
    started_at = utc_now()
    tests: list[dict[str, Any]] = []
    reset_hashes: list[str] = []

    for round_number in (1, 2):
        test_id = f"reset_round_{round_number}"
        workspace = workspace_root / test_id
        started = time.monotonic()
        initial_hash, execution = reset(case_dir, workspace)
        reset_hashes.append(initial_hash)
        evidence_path = evidence_root / f"{test_id}.json"
        write_json(
            evidence_path,
            {
                "schema_version": "case08_isolation_validation_evidence_v1",
                "test_id": test_id,
                "harness_exit_code": 0,
                "reset_execution": execution,
                "state_sha256": initial_hash,
            },
        )
        tests.append(
            test_record(
                test_id=test_id,
                kind="reset",
                executor="reset",
                expected="accept",
                observed="accept",
                harness_passed=True,
                duration_seconds=time.monotonic() - started,
                initial_hash=initial_hash,
                final_hash=initial_hash,
                evidence_ref=f"validation/evidence/{test_id}.json",
                notes="独立重置从公开 fixture 生成工作区；未创建候选执行沙箱。",
            )
        )

    for test_id, kind, preparation, expected in VERIFIER_TESTS:
        started = time.monotonic()
        workspace = workspace_root / test_id
        initial_hash, reset_execution = reset(case_dir, workspace)
        reset_hashes.append(initial_hash)
        preparation_execution = apply_candidate(case_dir, workspace, preparation)
        entry = attempts[test_id]
        verdict_path = verdict_root / f"{test_id}.json"
        controller_execution = command(
            [
                sys.executable,
                str(case_dir / "verifier" / "controller.py"),
                "--run-id",
                run_id,
                "--task-id",
                task_id,
                "--host-alias",
                host_alias,
                "--attempt-id",
                test_id,
                "--container-id",
                str(entry["container_id"]),
                "--container-name",
                str(entry["name"]),
                "--image-id",
                image_id,
                "--submitted-workspace",
                str(workspace),
                "--sandbox-contract",
                sandbox_contract,
                "--runtime-root",
                runtime_root,
                "--runtime-workspace",
                str(entry["runtime_workspace"]),
                "--fixture-root",
                str(case_dir / "fixtures" / "repository"),
                "--initial-state-sha256",
                initial_hash,
                "--output",
                str(verdict_path),
            ],
            timeout=150,
        )
        verdict = read_json(verdict_path)
        accepted = verdict.get("accepted") is True
        observed = "accept" if accepted else "reject"
        expected_verifier_exit = 0 if expected == "accept" else 1
        verifier_exit = int(controller_execution["exit_code"])
        signature_ok, signature = verifier_signature(test_id, verdict)
        harness_passed = (
            observed == expected
            and verifier_exit == expected_verifier_exit
            and signature_ok
        )
        harness_exit_code = 0 if harness_passed else 1
        evidence_path = evidence_root / f"{test_id}.json"
        write_json(
            evidence_path,
            {
                "schema_version": "case08_isolation_validation_evidence_v1",
                "test_id": test_id,
                "expected_verdict": expected,
                "observed_verdict": observed,
                "harness_exit_code": harness_exit_code,
                "verifier_exit_code": verifier_exit,
                "expected_verifier_exit_code": expected_verifier_exit,
                "verifier_signature": signature,
                "reset_execution": reset_execution,
                "preparation_execution": preparation_execution,
                "controller_execution": controller_execution,
                "verifier_result": verdict,
            },
        )
        tests.append(
            test_record(
                test_id=test_id,
                kind=kind,
                executor="oracle" if kind == "positive" else "verifier_test",
                expected=expected,
                observed=observed,
                harness_passed=harness_passed,
                duration_seconds=time.monotonic() - started,
                initial_hash=initial_hash,
                final_hash=str(verdict["final_state_sha256"]),
                evidence_ref=f"validation/evidence/{test_id}.json",
                notes=(
                    "报告行记录 harness 退出码；候选验收器原始退出码保存在 evidence。"
                ),
            )
        )

    summary = summarize(tests)
    deterministic_reset = len(set(reset_hashes)) == 1
    all_passed = deterministic_reset and summary["failed"] == 0
    verifier_sha256 = hashlib.sha256(
        (case_dir / "verifier" / "controller.py").read_bytes()
    ).hexdigest()
    finished_at = utc_now()
    report = {
        "schema_version": "nami_work_env_validation_report_v1",
        "run_id": "case08_isolation_v2_validation_v1",
        "task_id": "case_08",
        "case_version": CASE_VERSION,
        "started_at": started_at,
        "finished_at": finished_at,
        "status": "passed" if all_passed else "failed",
        "environment": {
            "host_id": args.host_id,
            "image_digest": image_id,
            "verifier_sha256": verifier_sha256,
        },
        "tests": tests,
        "summary": summary,
    }
    write_json(result_root / "validation_report.json", report)
    write_json(
        result_root / "remote_results.json",
        {
            "schema_version": "case08_isolation_remote_validation_raw_v1",
            "host_id": args.host_id,
            "image_id": image_id,
            "started_at": started_at,
            "finished_at": finished_at,
            "deterministic_reset": deterministic_reset,
            "initial_state_sha256": reset_hashes[0],
            "test_count": len(tests),
            "status": report["status"],
            "tests": tests,
        },
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "test_count": len(tests),
                "initial_state_sha256": reset_hashes[0],
            },
            sort_keys=True,
        )
    )
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
