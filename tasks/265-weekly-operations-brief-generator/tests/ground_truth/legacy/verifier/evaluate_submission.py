#!/usr/bin/env python3
"""候选验收聚合器：在隔离沙箱中真实执行脚本并关闭全部硬门。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any


STABLE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,80}$")
PLAN_SCHEMA = "case11_execution_ownership_plan_v2"
RESET_SCHEMA = "case11_reset_result_v2"
BASELINE_SCHEMA = "case11_reset_baseline_v2"
RESULT_SCHEMA = "case11_submission_evaluation_v2"
CASE_ROOT = Path(__file__).resolve().parents[1]
RESET = CASE_ROOT / "environment/reset.py"
CONTROLLER = CASE_ROOT / "environment/sandbox_controller.py"
CONTRACT = CASE_ROOT / "environment/sandbox_contract.json"
TERMINAL_VERIFIER = CASE_ROOT / "verifier/verify_outputs.py"
INVALID_VARIANTS = (
    "invalid_missing_column",
    "invalid_extra_cell",
    "invalid_date",
    "invalid_numeric",
    "invalid_duplicate",
    "invalid_logic",
    "invalid_zero_denominator",
)
OUTPUT_NAMES = ("summary.json", "weekly_brief.md")
ZERO_HASH = "0" * 64


class EvaluationError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_object(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise EvaluationError("JSON 必须是非链接普通文件")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise EvaluationError("JSON 根必须是对象")
    return value


def write_new_json(path: Path, value: dict[str, Any]) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
    try:
        os.write(descriptor, payload.encode("utf-8"))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def run(command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def safe_tag(evaluation_id: str, gate: str) -> str:
    digest = hashlib.sha256(f"{evaluation_id}:{gate}".encode("utf-8")).hexdigest()[:12]
    slug = re.sub(r"[^a-z0-9]+", "-", gate.lower()).strip("-")[:28]
    return f"ev-{digest}-{slug}"


def validate_plan(plan_path: Path, plan: dict[str, Any]) -> tuple[Path, Path, Path]:
    if plan.get("schema_version") != PLAN_SCHEMA:
        raise EvaluationError("ownership plan 版本无效")
    if plan_path.name != "ownership_plan.json" or plan_path.parent.name != "control":
        raise EvaluationError("ownership plan 位置无效")
    runtime_root = plan_path.parent.parent.resolve(strict=True)
    attempts_root = Path(str(plan.get("attempts_root", ""))).resolve(strict=True)
    evidence_root = Path(str(plan.get("evidence_root", ""))).resolve(strict=True)
    if Path(str(plan.get("runtime_root", ""))).resolve(strict=True) != runtime_root:
        raise EvaluationError("runtime_root 不一致")
    if attempts_root != runtime_root / "attempts" or evidence_root != runtime_root / "evidence":
        raise EvaluationError("动态子目录无效")
    if plan.get("contract_sha256") != sha256_file(CONTRACT):
        raise EvaluationError("plan 未锁定当前 contract")
    return runtime_root, attempts_root, evidence_root


def input_manifest(
    workspace: Path,
    baseline_path: Path,
    candidate_hash: str,
    output_path: Path,
) -> Path:
    baseline = read_object(baseline_path)
    if baseline.get("schema_version") != BASELINE_SCHEMA:
        raise EvaluationError("reset baseline 版本无效")
    states = baseline.get("input_files")
    if not isinstance(states, dict) or len(states) != 3:
        raise EvaluationError("reset baseline 输入状态无效")
    hashes = {relative: item["sha256"] for relative, item in states.items() if isinstance(item, dict)}
    if len(hashes) != 3:
        raise EvaluationError("reset baseline 输入哈希无效")
    script = workspace / "submission/generate_brief.py"
    if sha256_file(script) != candidate_hash:
        raise EvaluationError("候选脚本在验收期间发生变化")
    write_new_json(
        output_path,
        {
            "schema_version": "case11_expected_workspace_v2",
            "input_sha256": hashes,
            "input_state": states,
            "submission_sha256": candidate_hash,
        },
    )
    return output_path


class Evaluation:
    def __init__(self, plan_path: Path, submission_workspace: Path, evaluation_id: str, result_path: Path):
        self.plan_path = plan_path.resolve(strict=True)
        self.plan = read_object(self.plan_path)
        _, self.attempts_root, self.remote_evidence = validate_plan(self.plan_path, self.plan)
        self.submission_workspace = submission_workspace.resolve(strict=True)
        if self.submission_workspace.parent != self.attempts_root or self.submission_workspace.is_symlink() or not self.submission_workspace.is_dir():
            raise EvaluationError("submission workspace 必须是 attempts_root 的直接非链接子目录")
        self.evaluation_id = evaluation_id
        evaluations_root = self.remote_evidence / "evaluations"
        evaluations_root.mkdir(mode=0o2770, exist_ok=True)
        self.evidence_dir = evaluations_root / evaluation_id
        self.evidence_dir.mkdir(mode=0o2770)
        self.result_path = result_path.resolve()
        if self.result_path.parent != self.evidence_dir or self.result_path.exists() or self.result_path.is_symlink():
            raise EvaluationError("result 必须是本次 evaluation 目录内的新文件")
        script = self.submission_workspace / "submission/generate_brief.py"
        if script.is_symlink() or not script.is_file() or not stat.S_ISREG(script.lstat().st_mode):
            raise EvaluationError("候选脚本缺失或不是普通文件")
        self.candidate_bytes = script.read_bytes()
        if not 1 <= len(self.candidate_bytes) <= 131072:
            raise EvaluationError("候选脚本大小无效")
        try:
            source = self.candidate_bytes.decode("utf-8")
            compile(source, script.as_posix(), "exec")
        except (UnicodeError, SyntaxError) as exc:
            raise EvaluationError("候选脚本不是有效 UTF-8 Python") from exc
        self.candidate_hash = sha256_bytes(self.candidate_bytes)
        self.gates: list[dict[str, Any]] = []
        self.sandbox_clean = True

    def baseline_for(self, workspace_id: str) -> Path:
        path = self.remote_evidence / "reset_baselines" / f"{workspace_id}.json"
        return path.resolve(strict=True)

    def add_gate(self, gate_id: str, passed: bool, detail: str, evidence_refs: list[str]) -> None:
        self.gates.append(
            {
                "check_id": gate_id,
                "passed": bool(passed),
                "detail": detail,
                "evidence_refs": evidence_refs,
            }
        )

    def reset(self, gate: str, variant: str) -> tuple[str, Path, dict[str, Any]]:
        workspace_id = safe_tag(self.evaluation_id, gate)
        completed = run(
            [
                sys.executable,
                RESET.as_posix(),
                "--plan",
                self.plan_path.as_posix(),
                "--workspace-id",
                workspace_id,
                "--variant",
                variant,
            ],
            timeout=20,
        )
        if completed.returncode != 0:
            raise EvaluationError(f"reset 失败：{gate}:{completed.stderr[-160:]}")
        value = json.loads(completed.stdout)
        if not isinstance(value, dict) or value.get("schema_version") != RESET_SCHEMA or value.get("workspace_id") != workspace_id:
            raise EvaluationError("reset 结果无效")
        workspace = (self.attempts_root / workspace_id).resolve(strict=True)
        return workspace_id, workspace, value

    def install(self, workspace: Path) -> None:
        script = workspace / "submission/generate_brief.py"
        descriptor = os.open(script, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        try:
            os.write(descriptor, self.candidate_bytes)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def terminal_verify(self, workspace_id: str, workspace: Path, gate: str) -> dict[str, Any]:
        expected = input_manifest(
            workspace,
            self.baseline_for(workspace_id),
            self.candidate_hash,
            self.evidence_dir / f"{gate}.expected.json",
        )
        result = self.evidence_dir / f"{gate}.terminal.json"
        completed = run(
            [
                sys.executable,
                TERMINAL_VERIFIER.as_posix(),
                "--workspace",
                workspace.as_posix(),
                "--expected-input-manifest",
                expected.as_posix(),
                "--result",
                result.as_posix(),
            ],
            timeout=30,
        )
        value = read_object(result)
        value["process_exit_code"] = completed.returncode
        return value

    def sandbox(self, workspace_id: str, gate: str) -> dict[str, Any]:
        invocation_id = safe_tag(self.evaluation_id, f"{gate}-run")
        completed = run(
            [
                sys.executable,
                CONTROLLER.as_posix(),
                "--contract",
                CONTRACT.as_posix(),
                "--plan",
                self.plan_path.as_posix(),
                "--attempt-id",
                workspace_id,
                "--invocation-id",
                invocation_id,
            ],
            timeout=50,
        )
        source = self.remote_evidence / f"{invocation_id}.sandbox.json"
        if not source.is_file() or source.is_symlink():
            raise EvaluationError(f"sandbox 未生成证据：{gate}")
        value = read_object(source)
        value["controller_process_exit_code"] = completed.returncode
        persistent = self.evidence_dir / f"{gate}.sandbox.json"
        write_new_json(persistent, value)
        clean = self.sandbox_contract_passed(value)
        self.sandbox_clean = self.sandbox_clean and clean
        return value

    @staticmethod
    def sandbox_contract_passed(value: dict[str, Any]) -> bool:
        container_id = value.get("container_id")
        container_name = value.get("container_name")
        return (
            value.get("controller_status") == "passed"
            and value.get("controller_process_exit_code") == 0
            and not value.get("preflight_contract_errors")
            and not value.get("postflight_contract_errors")
            and value.get("creation_predeclared") is True
            and value.get("started_container") is True
            and value.get("timed_out") is False
            and value.get("quota_exceeded") is False
            and value.get("entry_limit_exceeded") is False
            and value.get("log_limit_exceeded") is False
            and value.get("inventory_scan_failed") is False
            and value.get("controller_error") is None
            and isinstance(container_id, str)
            and re.fullmatch(r"[0-9a-f]{64}", container_id) is not None
            and isinstance(container_name, str)
            and bool(container_name)
        )

    @staticmethod
    def output_hashes(workspace: Path) -> dict[str, str]:
        result: dict[str, str] = {}
        for name in OUTPUT_NAMES:
            path = workspace / "output" / name
            result[name] = sha256_file(path) if path.is_file() and not path.is_symlink() else ZERO_HASH
        return result

    @staticmethod
    def output_bytes(workspace: Path) -> dict[str, bytes | None]:
        result: dict[str, bytes | None] = {}
        for name in OUTPUT_NAMES:
            path = workspace / "output" / name
            if path.is_symlink() or not path.exists() or not stat.S_ISREG(path.lstat().st_mode):
                result[name] = None
            else:
                result[name] = path.read_bytes()
        return result

    @staticmethod
    def seed_last_known_good_outputs(workspace: Path) -> None:
        output_dir = workspace / "output"
        if output_dir.is_symlink() or not output_dir.is_dir() or any(output_dir.iterdir()):
            raise EvaluationError("last-known-good 只能写入全新空 output")
        for name in OUTPUT_NAMES:
            source = CASE_ROOT / "oracle/reference_output" / name
            payload = source.read_bytes()
            destination = output_dir / name
            descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
            try:
                os.write(descriptor, payload)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    def verify_submission_state(self) -> None:
        workspace_id = self.submission_workspace.name
        terminal = self.terminal_verify(workspace_id, self.submission_workspace, "submission_state")
        passed = terminal.get("status") == "passed" and terminal.get("process_exit_code") == 0
        self.add_gate(
            "submission_terminal_state",
            passed,
            "Agent 最终 workspace 必须包含正确、完整且未越界的交付物。",
            ["submission_state.terminal.json"],
        )

    def primary_and_idempotency(self) -> None:
        workspace_id, workspace, _ = self.reset("primary", "primary")
        self.install(workspace)
        first = self.sandbox(workspace_id, "primary_run_1")
        first_terminal = self.terminal_verify(workspace_id, workspace, "primary_run_1")
        first_hashes = self.output_hashes(workspace)
        first_pass = first.get("candidate_exit_code") == 0 and first.get("controller_status") == "passed" and first_terminal.get("status") == "passed"
        self.add_gate("fresh_primary_run_1", first_pass, "候选脚本必须在全新主 fixture 上真实执行成功。", ["primary_run_1.sandbox.json", "primary_run_1.terminal.json"])
        second = self.sandbox(workspace_id, "primary_run_2")
        second_terminal = self.terminal_verify(workspace_id, workspace, "primary_run_2")
        second_hashes = self.output_hashes(workspace)
        second_pass = second.get("candidate_exit_code") == 0 and second.get("controller_status") == "passed" and second_terminal.get("status") == "passed"
        self.add_gate("fresh_primary_run_2", second_pass, "同一 workspace 第二次执行仍必须成功。", ["primary_run_2.sandbox.json", "primary_run_2.terminal.json"])
        hashes_path = self.evidence_dir / "primary_idempotency.json"
        write_new_json(hashes_path, {"first_hashes": first_hashes, "second_hashes": second_hashes})
        self.add_gate("byte_idempotency", first_hashes == second_hashes and ZERO_HASH not in first_hashes.values(), "两次执行的两份输出必须逐字节一致。", ["primary_idempotency.json"])

    def hidden_generalization(self) -> None:
        workspace_id, workspace, _ = self.reset("alternate", "alternate")
        self.install(workspace)
        sandbox = self.sandbox(workspace_id, "alternate")
        terminal = self.terminal_verify(workspace_id, workspace, "alternate")
        passed = sandbox.get("candidate_exit_code") == 0 and sandbox.get("controller_status") == "passed" and terminal.get("status") == "passed"
        self.add_gate("hidden_generalization", passed, "脚本必须在隐藏周期、渠道、数值和模板上复用。", ["alternate.sandbox.json", "alternate.terminal.json"])

    def minimal_valid_generalization(self) -> None:
        workspace_id, workspace, _ = self.reset("minimal_valid", "minimal_valid")
        self.install(workspace)
        sandbox = self.sandbox(workspace_id, "minimal_valid")
        terminal = self.terminal_verify(workspace_id, workspace, "minimal_valid")
        passed = sandbox.get("candidate_exit_code") == 0 and sandbox.get("controller_status") == "passed" and terminal.get("status") == "passed"
        self.add_gate(
            "minimal_valid_generalization",
            passed,
            "脚本必须接受公开合同允许的四行最小合法数据，不能按样本行数投机拒绝。",
            ["minimal_valid.sandbox.json", "minimal_valid.terminal.json"],
        )

    def invalid_inputs(self) -> None:
        variant_results: list[bool] = []
        for variant in INVALID_VARIANTS:
            workspace_id, workspace, _ = self.reset(variant, variant)
            self.install(workspace)
            sandbox = self.sandbox(workspace_id, variant)
            outputs = sorted(path.name for path in (workspace / "output").iterdir())
            passed = (
                self.sandbox_contract_passed(sandbox)
                and isinstance(sandbox.get("candidate_exit_code"), int)
                and sandbox["candidate_exit_code"] != 0
                and not outputs
            )
            variant_results.append(passed)
            output_path = self.evidence_dir / f"{variant}.atomicity.json"
            write_new_json(
                output_path,
                {
                    "candidate_exit_code": sandbox.get("candidate_exit_code"),
                    "output_entries": outputs,
                    "sandbox_contract_passed": self.sandbox_contract_passed(sandbox),
                    "timed_out": sandbox.get("timed_out"),
                },
            )
            self.add_gate(
                variant,
                passed,
                "异常输入必须在时限内由候选主动非零退出、满足完整 sandbox 合同且 output/ 保持为空。",
                [f"{variant}.sandbox.json", f"{variant}.atomicity.json"],
            )
        self.add_gate(
            "invalid_input_atomicity",
            len(variant_results) == len(INVALID_VARIANTS) and all(variant_results),
            "七类异常输入必须全部在时限内 fail-closed，且不得残留任何输出。",
            [f"{variant}.sandbox.json" for variant in INVALID_VARIANTS]
            + [f"{variant}.atomicity.json" for variant in INVALID_VARIANTS],
        )

    def invalid_input_preserves_existing_outputs(self) -> None:
        variant = "invalid_duplicate"
        gate = "invalid_existing_outputs"
        workspace_id, workspace, _ = self.reset(gate, variant)
        self.install(workspace)
        self.seed_last_known_good_outputs(workspace)
        before = self.output_bytes(workspace)
        before_hashes = self.output_hashes(workspace)
        sandbox = self.sandbox(workspace_id, gate)
        after = self.output_bytes(workspace)
        after_hashes = self.output_hashes(workspace)
        output_dir = workspace / "output"
        entries = sorted(path.name for path in output_dir.iterdir()) if output_dir.is_dir() and not output_dir.is_symlink() else []
        byte_equal = {
            name: before[name] is not None and after[name] is not None and before[name] == after[name]
            for name in OUTPUT_NAMES
        }
        passed = (
            self.sandbox_contract_passed(sandbox)
            and isinstance(sandbox.get("candidate_exit_code"), int)
            and sandbox["candidate_exit_code"] != 0
            and entries == sorted(OUTPUT_NAMES)
            and all(byte_equal.values())
        )
        evidence = self.evidence_dir / f"{gate}.atomicity.json"
        write_new_json(
            evidence,
            {
                "candidate_exit_code": sandbox.get("candidate_exit_code"),
                "fixture_variant": variant,
                "output_entries": entries,
                "before_sha256": before_hashes,
                "after_sha256": after_hashes,
                "byte_equal": byte_equal,
                "sandbox_contract_passed": self.sandbox_contract_passed(sandbox),
                "timed_out": sandbox.get("timed_out"),
            },
        )
        self.add_gate(
            "invalid_existing_output_atomicity",
            passed,
            "代表性异常输入必须非零退出，且不得删除、改写或新增 last-known-good 的两份既有完整输出。",
            [f"{gate}.sandbox.json", f"{gate}.atomicity.json"],
        )

    def finish(self) -> dict[str, Any]:
        self.add_gate("sandbox_contract", self.sandbox_clean, "所有候选 invocation 均须满足静态合同、资源预登记、配额与静默终态。", [item.name for item in sorted(self.evidence_dir.glob("*.sandbox.json"))])
        passed = all(item["passed"] for item in self.gates)
        return {
            "schema_version": RESULT_SCHEMA,
            "status": "passed" if passed else "failed",
            "evaluation_id": self.evaluation_id,
            "candidate_script_sha256": self.candidate_hash,
            "checks": self.gates,
            "summary": {
                "total": len(self.gates),
                "passed": sum(item["passed"] for item in self.gates),
                "failed": sum(not item["passed"] for item in self.gates),
            },
        }


def invalid_result(evaluation_id: str, exc: BaseException) -> dict[str, Any]:
    return {
        "schema_version": RESULT_SCHEMA,
        "status": "invalid",
        "evaluation_id": evaluation_id,
        "candidate_script_sha256": ZERO_HASH,
        "checks": [{"check_id": "evaluation_precondition", "passed": False, "detail": type(exc).__name__, "evidence_refs": []}],
        "summary": {"total": 1, "passed": 0, "failed": 1},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--submission-workspace", type=Path, required=True)
    parser.add_argument("--evaluation-id", required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    if not STABLE.fullmatch(args.evaluation_id):
        print("evaluation ID 无效", file=sys.stderr)
        return 2
    evaluation: Evaluation | None = None
    try:
        evaluation = Evaluation(args.plan, args.submission_workspace, args.evaluation_id, args.result)
        evaluation.verify_submission_state()
        evaluation.primary_and_idempotency()
        evaluation.hidden_generalization()
        evaluation.minimal_valid_generalization()
        evaluation.invalid_inputs()
        evaluation.invalid_input_preserves_existing_outputs()
        result = evaluation.finish()
        write_new_json(evaluation.result_path, result)
    except (EvaluationError, OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        if evaluation is None:
            print(f"验收初始化失败：{type(exc).__name__}", file=sys.stderr)
            return 2
        result = invalid_result(args.evaluation_id, exc)
        if not evaluation.result_path.exists():
            write_new_json(evaluation.result_path, result)
    sys.stdout.write(json.dumps({"status": result["status"], "summary": result["summary"]}, ensure_ascii=False, sort_keys=True) + "\n")
    return 0 if result["status"] == "passed" else 1 if result["status"] == "failed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
