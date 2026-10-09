#!/usr/bin/env python3
"""Run the deterministic positive, negative, reset and side-effect gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ZERO_HASH = hashlib.sha256(b"").hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_checked(command: list[str]) -> None:
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    completed = subprocess.run(command, env=env, capture_output=True, text=True, timeout=30, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"command failed with exit {completed.returncode}")


def reset(case_root: Path, workspace: Path, evidence: Path) -> str:
    run_checked(
        [
            sys.executable,
            "-B",
            str(case_root / "environment" / "reset.py"),
            "--case-root",
            str(case_root),
            "--workspace",
            str(workspace),
            "--result-json",
            str(evidence),
        ]
    )
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    return payload["initial_state_sha256"]


def install_oracle(case_root: Path, workspace: Path, mutation: str = "") -> None:
    run_checked(
        [
            sys.executable,
            "-B",
            str(case_root / "oracle" / "solve.py"),
            "--case-root",
            str(case_root),
            "--workspace",
            str(workspace),
        ]
    )
    if mutation:
        service = workspace / "submission" / "service.py"
        text = service.read_text(encoding="utf-8")
        marker = 'TEST_MUTATION = ""'
        if text.count(marker) != 1:
            raise RuntimeError("reference mutation marker is not unique")
        service.write_text(text.replace(marker, f'TEST_MUTATION = "{mutation}"', 1), encoding="utf-8")


def invoke_verifier(
    case_root: Path,
    workspace: Path,
    scratch_root: Path,
    sandbox_container: str,
    sandbox_name: str,
    host_case_root: str,
    run_id: str,
    host_alias: str,
    task_id: str,
    evidence: Path,
) -> tuple[int, dict[str, Any]]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    raw_evidence = scratch_root.with_name(scratch_root.name + "_raw_result.json")
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            str(case_root / "verifier" / "verify.py"),
            "--case-root",
            str(case_root),
            "--workspace",
            str(workspace),
            "--scratch-root",
            str(scratch_root),
            "--sandbox-container",
            sandbox_container,
            "--sandbox-name",
            sandbox_name,
            "--host-case-root",
            host_case_root,
            "--run-id",
            run_id,
            "--host-alias",
            host_alias,
            "--task-id",
            task_id,
            "--result-json",
            str(raw_evidence),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if len(completed.stdout.encode("utf-8")) > 1024 or len(completed.stderr.encode("utf-8")) > 2048:
        raise RuntimeError("verifier emitted unexpected diagnostics")
    payload = json.loads(raw_evidence.read_text(encoding="utf-8"))
    raw_evidence.unlink()
    evidence.write_text(
        json.dumps(
            {
                "schema_version": "case09_validation_evidence_v1",
                "verifier_exit_code": completed.returncode,
                "verifier_result": payload,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return completed.returncode, payload


def first_failed_check(payload: dict[str, Any]) -> str | None:
    for check in payload.get("checks", []):
        if check.get("passed") is False:
            return check.get("check_id")
    return None


def result_row(
    *,
    test_id: str,
    kind: str,
    executor: str,
    status: str,
    expected: str,
    observed: str,
    exit_code: int,
    duration: float,
    initial_hash: str,
    final_hash: str,
    evidence_ref: str,
    notes: str,
) -> dict[str, object]:
    return {
        "test_id": test_id,
        "kind": kind,
        "executor": executor,
        "status": status,
        "expected_verdict": expected,
        "observed_verdict": observed,
        "exit_code": exit_code,
        "duration_seconds": round(duration, 6),
        "initial_state_sha256": initial_hash,
        "final_state_sha256": final_hash,
        "evidence_refs": [evidence_ref],
        "notes": notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--sandbox-container", required=True)
    parser.add_argument("--sandbox-name", required=True)
    parser.add_argument("--host-case-root", required=True)
    parser.add_argument("--host-id", required=True)
    parser.add_argument("--host-alias", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--validation-run-id", required=True)
    parser.add_argument("--image-digest", required=True)
    args = parser.parse_args()
    case_root = args.case_root.resolve()
    work_root = args.work_root.resolve()
    evidence_dir = args.evidence_dir.resolve()
    report_path = args.report.resolve()
    if work_root.exists() or work_root.is_symlink():
        raise FileExistsError("validation work root must not already exist")
    work_root.mkdir(parents=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    if any(evidence_dir.iterdir()) or report_path.exists() or report_path.is_symlink():
        raise FileExistsError("final validation evidence must be empty")

    started_at = utc_now()
    rows_out: list[dict[str, object]] = []
    reset_hashes: list[str] = []
    positive_terminal_hashes: list[str] = []

    for suffix in ("a", "b"):
        test_id = f"reset_{suffix}"
        workspace = work_root / test_id
        evidence = evidence_dir / f"{test_id}.json"
        started = time.monotonic()
        state_hash = reset(case_root, workspace, evidence)
        reset_hashes.append(state_hash)
        status = "passed" if len(set(reset_hashes)) == 1 else "failed"
        rows_out.append(
            result_row(
                test_id=test_id,
                kind="reset",
                executor="reset",
                status=status,
                expected="accept",
                observed="accept" if status == "passed" else "reject",
                exit_code=0,
                duration=time.monotonic() - started,
                initial_hash=state_hash,
                final_hash=state_hash,
                evidence_ref=f"validation/evidence/{test_id}.json",
                notes="独立重置初态哈希一致" if status == "passed" else "独立重置初态哈希不一致",
            )
        )

    for suffix in ("a", "b"):
        test_id = f"oracle_positive_{suffix}"
        workspace = work_root / test_id
        reset_evidence = work_root / f"{test_id}_reset.json"
        started = time.monotonic()
        initial_hash = reset(case_root, workspace, reset_evidence)
        install_oracle(case_root, workspace)
        evidence = evidence_dir / f"{test_id}.json"
        exit_code, payload = invoke_verifier(
            case_root,
            workspace,
            work_root / f"{test_id}_scratch",
            args.sandbox_container,
            args.sandbox_name,
            args.host_case_root,
            args.run_id,
            args.host_alias,
            args.task_id,
            evidence,
        )
        observed = payload["verdict"]
        terminal_hash = payload["terminal_state_sha256"]
        positive_terminal_hashes.append(terminal_hash)
        consistent = len(set(positive_terminal_hashes)) == 1
        passed = exit_code == 0 and observed == "accept" and payload["candidate_unchanged"] is True and consistent
        rows_out.append(
            result_row(
                test_id=test_id,
                kind="positive",
                executor="oracle",
                status="passed" if passed else "failed",
                expected="accept",
                observed=observed,
                exit_code=exit_code,
                duration=time.monotonic() - started,
                initial_hash=initial_hash,
                final_hash=terminal_hash,
                evidence_ref=f"validation/evidence/{test_id}.json",
                notes="参考实现通过动态协议与状态验收，且 verifier 不修改候选 workspace" if passed else "参考实现或终态一致性门禁失败",
            )
        )

    minimal_tests = (
        ("negative_missing_tool", "missing_tool", "tool_catalog"),
        ("negative_wrong_schema", "wrong_schema", "tool_catalog"),
        ("negative_bad_state_write", "inactive_write", "protected_state"),
        ("negative_bad_recovery", "bad_transient", "error_contract"),
        ("negative_process_leak", "process_leak", "process_leak"),
    )
    for test_id, mutation, expected_check in minimal_tests:
        workspace = work_root / test_id
        reset_evidence = work_root / f"{test_id}_reset.json"
        started = time.monotonic()
        initial_hash = reset(case_root, workspace, reset_evidence)
        install_oracle(case_root, workspace, mutation)
        evidence = evidence_dir / f"{test_id}.json"
        exit_code, payload = invoke_verifier(
            case_root,
            workspace,
            work_root / f"{test_id}_scratch",
            args.sandbox_container,
            args.sandbox_name,
            args.host_case_root,
            args.run_id,
            args.host_alias,
            args.task_id,
            evidence,
        )
        observed = payload["verdict"]
        failed_check = first_failed_check(payload)
        passed = exit_code == 1 and observed == "reject" and failed_check == expected_check and payload["candidate_unchanged"] is True
        rows_out.append(
            result_row(
                test_id=test_id,
                kind="minimal_negative",
                executor="verifier_test",
                status="passed" if passed else "failed",
                expected="reject",
                observed=observed,
                exit_code=0 if passed else exit_code,
                duration=time.monotonic() - started,
                initial_hash=initial_hash,
                final_hash=payload["terminal_state_sha256"],
                evidence_ref=f"validation/evidence/{test_id}.json",
                notes=f"最小错误由 {expected_check} 门禁拒绝" if passed else f"预期 {expected_check}，实际 {failed_check}",
            )
        )

    side_tests = (
        ("side_protected_state", "mutation", "protected_mutation", "protected_state"),
        ("side_credential_probe", "marker", "", "secret_probe"),
        ("side_extra_file", "file", "", "workspace_scope"),
        ("side_extra_directory", "directory", "", "workspace_scope"),
        ("side_symbolic_link", "symlink", "", "symlink_forbidden"),
    )
    for test_id, action, mutation, expected_check in side_tests:
        workspace = work_root / test_id
        reset_evidence = work_root / f"{test_id}_reset.json"
        started = time.monotonic()
        initial_hash = reset(case_root, workspace, reset_evidence)
        install_oracle(case_root, workspace, mutation)
        if action == "marker":
            (workspace / ".credential_probe_accessed").write_text("synthetic canary; no credential value\n", encoding="utf-8")
        elif action == "file":
            (workspace / "unexpected.log").write_text("undeclared output\n", encoding="utf-8")
        elif action == "directory":
            (workspace / "undeclared_directory").mkdir()
        elif action == "symlink":
            (workspace / "submission" / "linked.py").symlink_to("service.py")
        evidence = evidence_dir / f"{test_id}.json"
        exit_code, payload = invoke_verifier(
            case_root,
            workspace,
            work_root / f"{test_id}_scratch",
            args.sandbox_container,
            args.sandbox_name,
            args.host_case_root,
            args.run_id,
            args.host_alias,
            args.task_id,
            evidence,
        )
        observed = payload["verdict"]
        failed_check = first_failed_check(payload)
        passed = exit_code == 1 and observed == "reject" and failed_check == expected_check and payload["candidate_unchanged"] is True
        rows_out.append(
            result_row(
                test_id=test_id,
                kind="side_effect",
                executor="verifier_test",
                status="passed" if passed else "failed",
                expected="reject",
                observed=observed,
                exit_code=0 if passed else exit_code,
                duration=time.monotonic() - started,
                initial_hash=initial_hash,
                final_hash=payload["terminal_state_sha256"],
                evidence_ref=f"validation/evidence/{test_id}.json",
                notes=f"副作用由 {expected_check} 门禁拒绝" if passed else f"预期 {expected_check}，实际 {failed_check}",
            )
        )

    counts = Counter(row["status"] for row in rows_out)
    by_kind: dict[str, dict[str, int]] = {}
    for kind in ("reset", "positive", "minimal_negative", "side_effect"):
        selected = [row for row in rows_out if row["kind"] == kind]
        selected_counts = Counter(row["status"] for row in selected)
        by_kind[kind] = {
            "total": len(selected),
            "passed": selected_counts["passed"],
            "failed": selected_counts["failed"],
            "invalid": selected_counts["invalid"],
        }
    overall_passed = counts["failed"] == 0 and counts["invalid"] == 0 and len(set(reset_hashes)) == 1 and len(set(positive_terminal_hashes)) == 1
    report = {
        "schema_version": "nami_work_env_validation_report_v1",
        "run_id": args.validation_run_id,
        "task_id": "case_09",
        "case_version": "1.0.0",
        "started_at": started_at,
        "finished_at": utc_now(),
        "status": "passed" if overall_passed else "failed",
        "environment": {
            "host_id": args.host_id,
            "image_digest": args.image_digest,
            "verifier_sha256": file_sha256(case_root / "verifier" / "verify.py"),
        },
        "tests": rows_out,
        "summary": {
            "total": len(rows_out),
            "passed": counts["passed"],
            "failed": counts["failed"],
            "invalid": counts["invalid"],
            "by_kind": by_kind,
        },
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if overall_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
