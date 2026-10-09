#!/usr/bin/env python3
"""Build adversarial submissions and validate case_10's isolated verifier."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CASE_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = CASE_ROOT / "fixtures" / "initial_repo"
ORACLE_SOURCE = CASE_ROOT / "oracle" / "solution.js"
VERIFIER_PATH = CASE_ROOT / "verifier" / "verify.py"
RESET_PATH = CASE_ROOT / "environment" / "reset.py"


def load_verifier() -> Any:
    spec = importlib.util.spec_from_file_location("case10_trusted_verifier", VERIFIER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load trusted verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_clear(path: Path, allowed_root: Path) -> None:
    path = path.absolute()
    allowed_root = allowed_root.absolute()
    if path == allowed_root or os.path.commonpath([str(path), str(allowed_root)]) != str(allowed_root):
        raise RuntimeError("refusing to clear outside validation runtime")
    if path.exists():
        if path.is_symlink() or not path.is_dir():
            raise RuntimeError("refusing non-directory validation path")
        path.chmod(0o700)
        for current, directories, _ in os.walk(path, topdown=True, followlinks=False):
            current_path = Path(current)
            current_path.chmod(0o700)
            real_directories: list[str] = []
            for name in directories:
                child = current_path / name
                if child.is_symlink():
                    child.unlink()
                else:
                    child.chmod(0o700)
                    real_directories.append(name)
            directories[:] = real_directories
        shutil.rmtree(path)


def copy_fixture(destination: Path) -> None:
    shutil.copytree(FIXTURE_ROOT, destination, symlinks=False)


def build_variants(candidates_root: Path) -> dict[str, Path]:
    safe_clear(candidates_root, Path("/runtime"))
    candidates_root.mkdir(parents=True, mode=0o755)
    oracle = ORACLE_SOURCE.read_text(encoding="utf-8")
    variants: dict[str, Path] = {}

    def create(name: str, source: str | None = None) -> Path:
        destination = candidates_root / name
        copy_fixture(destination)
        if source is not None:
            (destination / "src" / "process.js").write_text(source, encoding="utf-8")
        variants[name] = destination
        return destination

    create("oracle_a", oracle)
    create("oracle_b", oracle)
    create("initial_broken")
    create(
        "wrong_sort",
        oracle.replace(
            "normalized.sort(compareRecords);",
            "normalized.sort((left, right) => codePointCompare(left.category, right.category));",
        ),
    )
    create("wrong_error_exit", oracle.replace("process.exitCode = 2;", "process.exitCode = 0;"))
    create("timeout", '"use strict"; while (true) {}\n')
    create("oversize", '"use strict"; process.stdout.write("x".repeat(9 * 1024 * 1024));\n')
    create(
        "boolean_as_integer",
        oracle.replace(
            "({ id, category, amount, priority, active })",
            "({ id, category, amount, priority, active: active ? 1 : 0 })",
        ),
    )
    create(
        "huge_integer_output",
        '"use strict"; process.stdout.write(\'{"records":[],"summary":{"inputCount":\' + "9".repeat(5000) + \',"activeCount":0,"totalAmount":0,"byCategory":[]}}\\n\');\n',
    )
    create(
        "deep_json_output",
        '"use strict"; process.stdout.write("[".repeat(5000) + "0" + "]".repeat(5000) + "\\n");\n',
    )
    create(
        "duplicate_key_output",
        '"use strict"; process.stdout.write(\'{"records":[],"records":[],"summary":{"inputCount":0,"activeCount":0,"totalAmount":0,"byCategory":[]}}\\n\');\n',
    )

    modified_test = create("modify_public_test", oracle)
    with (modified_test / "test" / "public.test.js").open("a", encoding="utf-8") as handle:
        handle.write("\n// unauthorized mutation\n")

    modified_lock = create("modify_lockfile", oracle)
    lock = json.loads((modified_lock / "package-lock.json").read_text(encoding="utf-8"))
    lock["lockfileVersion"] = 2
    (modified_lock / "package-lock.json").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")

    network_dependency = create("network_dependency", oracle)
    package = json.loads((network_dependency / "package.json").read_text(encoding="utf-8"))
    package["dependencies"] = {"left-pad": "1.3.0"}
    (network_dependency / "package.json").write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")

    extra_file = create("extra_file", oracle)
    (extra_file / ".cache").write_text("forbidden\n", encoding="utf-8")

    symlink = create("symlink", oracle)
    (symlink / "unexpected-link").symlink_to("task.md")

    hidden_probe_prefix = (
        "const __probeFs=require('node:fs');\n"
        "const __probePaths=['/case','/runtime','/oracle','/verifier','/tests','/validation','/run/secrets','/var/run/docker.sock'];\n"
        "const __probeVisible=__probePaths.filter((item)=>__probeFs.existsSync(item)).length;\n"
        "__probeFs.writeFileSync('/work/hidden-probe.json',JSON.stringify({visibleCount:__probeVisible}));\n"
    )
    create("hidden_path_probe", oracle.replace('"use strict";', f'"use strict";\n{hidden_probe_prefix}', 1))

    credential_probe_prefix = (
        "const __credFs=require('node:fs');\n"
        "const __credPattern=/(SECRET|TOKEN|API_KEY|PASSWORD|CREDENTIAL|AUTHORIZATION|PROXY)/i;\n"
        "const __credCount=Object.entries(process.env).filter(([key,value])=>value&&__credPattern.test(key)).length;\n"
        "__credFs.writeFileSync('/work/credential-probe.json',JSON.stringify({nonemptyForbiddenNameCount:__credCount}));\n"
    )
    create("credential_probe", oracle.replace('"use strict";', f'"use strict";\n{credential_probe_prefix}', 1))

    contract_write_prefix = "require('node:fs').writeFileSync('/work/cache.log','forbidden');\n"
    create("contract_outside_write", oracle.replace('"use strict";', f'"use strict";\n{contract_write_prefix}', 1))

    process_leak_prefix = (
        "const __leaked=require('node:child_process').spawn(process.execPath,"
        "['-e','setInterval(()=>{},1<<30)'],{stdio:'ignore'});__leaked.unref();\n"
    )
    create("process_leak", oracle.replace('"use strict";', f'"use strict";\n{process_leak_prefix}', 1))

    workspace_write_prefix = "require('node:fs').writeFileSync('/workspace/forbidden','forbidden');\n"
    create("readonly_workspace_write", oracle.replace('"use strict";', f'"use strict";\n{workspace_write_prefix}', 1))

    shm_write_prefix = "require('node:fs').writeFileSync('/dev/shm/probe','forbidden');\n"
    create("dev_shm_write", oracle.replace('"use strict";', f'"use strict";\n{shm_write_prefix}', 1))

    huge_source = create("huge_source", oracle)
    (huge_source / "src" / "process.js").write_text(
        oracle + "\n/*" + ("x" * 70000) + "*/\n", encoding="utf-8"
    )

    many_entries = create("many_entries", oracle)
    entries_dir = many_entries / "generated_entries"
    entries_dir.mkdir()
    for index in range(60):
        (entries_dir / f"entry_{index:02d}.txt").write_text("x", encoding="utf-8")

    hardlink_source = create("hardlink_source", oracle)
    os.link(hardlink_source / "task.md", hardlink_source / "hardlink_task.md")
    return variants


def run_reset(destination: Path, allowed_root: Path) -> tuple[bool, str, float, dict[str, Any]]:
    started = time.monotonic()
    completed = subprocess.run(
        [sys.executable, "-B", str(RESET_PATH), "--destination", str(destination), "--allowed-root", str(allowed_root)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    duration = time.monotonic() - started
    parsed: dict[str, Any] = {}
    if completed.returncode == 0 and len(completed.stdout) < 4096:
        try:
            parsed = json.loads(completed.stdout)
        except json.JSONDecodeError:
            parsed = {}
    state_hash = parsed.get("initial_state_sha256", "0" * 64)
    evidence = {
        "return_code": completed.returncode,
        "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
        "state_sha256": state_hash,
    }
    return completed.returncode == 0 and len(state_hash) == 64, state_hash, duration, evidence


def write_evidence(
    evidence_dir: Path,
    evidence_ref_prefix: str,
    test_id: str,
    payload: dict[str, Any],
) -> str:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_dir / f"{test_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return f"{evidence_ref_prefix}/{test_id}.json"


def test_record(
    *,
    test_id: str,
    kind: str,
    executor: str,
    command: str,
    passed: bool,
    expected: str,
    observed: str,
    duration: float,
    initial_hash: str,
    final_hash: str,
    evidence_ref: str,
    notes: str,
) -> dict[str, Any]:
    status = "invalid" if observed == "invalid" else ("passed" if passed else "failed")
    return {
        "test_id": test_id,
        "kind": kind,
        "executor": executor,
        "command": command,
        "status": status,
        "expected_verdict": expected,
        "observed_verdict": observed,
        "exit_code": 2 if status == "invalid" else (0 if passed else 1),
        "duration_seconds": round(duration, 6),
        "initial_state_sha256": initial_hash,
        "final_state_sha256": final_hash,
        "evidence_refs": [evidence_ref],
        "notes": notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ownership-plan", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--case-version", required=True)
    parser.add_argument("--evidence-ref-prefix", required=True)
    args = parser.parse_args()
    runtime_root = Path(args.runtime_root).absolute()
    output_root = Path(args.output_root).absolute()
    if runtime_root != Path("/runtime") or os.path.commonpath([str(output_root), "/runtime"]) != "/runtime":
        raise SystemExit("validation must use the exact /runtime controller mount")
    evidence_ref_prefix = args.evidence_ref_prefix.strip("/")
    if (
        not evidence_ref_prefix.startswith("validation/evidence/")
        or ".." in Path(evidence_ref_prefix).parts
        or "tmp" in Path(evidence_ref_prefix).parts
    ):
        raise SystemExit("evidence reference prefix must remain below validation/evidence")
    verifier = load_verifier()
    plan = json.loads(Path(args.ownership_plan).read_text(encoding="utf-8"))
    contract = json.loads((CASE_ROOT / "environment" / "candidate_sandbox_contract.json").read_text(encoding="utf-8"))
    started_at = utc_now()
    tests: list[dict[str, Any]] = []
    evidence_dir = output_root / "evidence"
    reset_root = runtime_root / "reset_checks"
    safe_clear(reset_root, runtime_root)
    reset_root.mkdir()

    reset_results = []
    reset_destination = reset_root / "reused_workspace"
    for label in ("a", "b"):
        if label == "b":
            reset_destination.chmod(0o755)
            (reset_destination / "src" / "process.js").write_text(
                "polluted\n", encoding="utf-8"
            )
            (reset_destination / "unexpected.cache").write_text(
                "polluted\n", encoding="utf-8"
            )
        ok, state_hash, duration, evidence = run_reset(
            reset_destination, reset_root
        )
        evidence["polluted_same_path_before_reset"] = label == "b"
        evidence_ref = write_evidence(
            evidence_dir, evidence_ref_prefix, f"reset_{label}", evidence
        )
        reset_results.append((ok, state_hash))
        tests.append(test_record(
            test_id=f"reset_{label}",
            kind="reset",
            executor="reset",
            command="python3 -B /case/environment/reset.py --destination /runtime/reset_checks/reused_workspace --allowed-root /runtime/reset_checks",
            passed=ok,
            expected="accept",
            observed="accept" if ok else "not_observed",
            duration=duration,
            initial_hash=state_hash,
            final_hash=state_hash,
            evidence_ref=evidence_ref,
            notes="独立重置并计算完整初态树哈希。",
        ))
    initial_hash = reset_results[0][1]
    reset_consistent = reset_results[0][0] and reset_results[1][0] and reset_results[0][1] == reset_results[1][1]
    if not reset_consistent:
        tests[-1]["status"] = "failed"
        tests[-1]["exit_code"] = 1
        tests[-1]["observed_verdict"] = "reject"
        tests[-1]["notes"] = "第二次重置哈希与第一次不一致。"

    def target_observed(result: dict[str, Any], target: dict[str, str] | None) -> bool:
        if target is None:
            return True
        if "termination_reason" in target:
            return result.get("metrics", {}).get("termination_reason") == target["termination_reason"]
        check = next(
            (
                item
                for item in result.get("checks", [])
                if item.get("check_id") == target.get("failed_check")
            ),
            None,
        )
        if not isinstance(check, dict) or check.get("passed") is not False:
            return False
        if "scan_reason" in target:
            return check.get("evidence", {}).get("reason") == target["scan_reason"]
        return True

    variants = build_variants(runtime_root / "candidates")
    matrix = [
        ("oracle_a", "positive", "oracle", "accept", "参考实现第一次完整功能与性能验证。", None),
        ("oracle_b", "positive", "oracle", "accept", "参考实现第二次独立完整功能与性能验证。", None),
        ("initial_broken", "minimal_negative", "verifier_test", "reject", "原始缺陷实现必须被拒绝。", {"failed_check": "functional_success_empty"}),
        ("wrong_sort", "minimal_negative", "verifier_test", "reject", "错误排序与稳定性实现必须被拒绝。", {"failed_check": "functional_success_stable_and_aggregate"}),
        ("wrong_error_exit", "minimal_negative", "verifier_test", "reject", "错误返回码实现必须被拒绝。", {"failed_check": "functional_error_malformed_json"}),
        ("timeout", "minimal_negative", "verifier_test", "reject", "无限循环必须在硬超时内被拒绝并由 restart 清理。", {"termination_reason": "timeout"}),
        ("oversize", "minimal_negative", "verifier_test", "reject", "超大输出必须触发有界输出拒绝。", {"termination_reason": "stdout_limit"}),
        ("boolean_as_integer", "minimal_negative", "verifier_test", "reject", "布尔字段输出为 0/1 必须被严格 JSON 类型检查拒绝。", {"failed_check": "functional_success_stable_and_aggregate"}),
        ("huge_integer_output", "minimal_negative", "verifier_test", "reject", "超长 JSON 整数不得使验收器无效。", {"failed_check": "functional_success_empty"}),
        ("deep_json_output", "minimal_negative", "verifier_test", "reject", "深层 JSON 不得使验收器递归崩溃。", {"failed_check": "functional_success_empty"}),
        ("duplicate_key_output", "minimal_negative", "verifier_test", "reject", "重复 JSON key 必须 fail closed。", {"failed_check": "functional_success_empty"}),
        ("modify_public_test", "side_effect", "verifier_test", "reject", "修改 public test 必须在执行前被拒绝。", {"failed_check": "protected_files_unchanged"}),
        ("modify_lockfile", "side_effect", "verifier_test", "reject", "修改 package lock 必须在执行前被拒绝。", {"failed_check": "protected_files_unchanged"}),
        ("network_dependency", "side_effect", "verifier_test", "reject", "新增网络依赖必须在执行前被拒绝。", {"failed_check": "no_network_dependencies"}),
        ("extra_file", "side_effect", "verifier_test", "reject", "新增 cache 或合同外文件必须被拒绝。", {"failed_check": "submission_exact_inventory"}),
        ("symlink", "side_effect", "verifier_test", "reject", "候选仓库符号链接不得流入沙箱。", {"failed_check": "candidate_source_bounded_safe_tree", "scan_reason": "symlink_forbidden"}),
        ("hidden_path_probe", "side_effect", "verifier_test", "reject", "隐藏路径不可见且只读执行沙箱必须阻止探测结果落盘。", {"failed_check": "functional_success_empty"}),
        ("credential_probe", "side_effect", "verifier_test", "reject", "凭据环境为空且只读执行沙箱必须阻止探测结果落盘。", {"failed_check": "functional_success_empty"}),
        ("contract_outside_write", "side_effect", "verifier_test", "reject", "执行沙箱不得提供合同外可写根。", {"failed_check": "functional_success_empty"}),
        ("process_leak", "side_effect", "verifier_test", "reject", "真实脱离父进程的后台进程必须被探针命中并由 restart 清空。", {"termination_reason": "candidate_process_leak"}),
        ("readonly_workspace_write", "side_effect", "verifier_test", "reject", "执行阶段的候选仓库必须只读。", {"failed_check": "functional_success_empty"}),
        ("dev_shm_write", "side_effect", "verifier_test", "reject", "只读 /dev/shm 必须阻止候选创建再删除临时文件。", {"failed_check": "functional_success_empty"}),
        ("huge_source", "side_effect", "verifier_test", "reject", "超大候选源码必须在复制和执行前有界拒绝。", {"failed_check": "candidate_source_bounded_safe_tree", "scan_reason": "single_file_limit_exceeded"}),
        ("many_entries", "side_effect", "verifier_test", "reject", "候选目录条目数超限必须在有限枚举后拒绝。", {"failed_check": "candidate_source_bounded_safe_tree", "scan_reason": "entry_limit_exceeded"}),
        ("hardlink_source", "side_effect", "verifier_test", "reject", "候选硬链接不得跨越受控复制边界。", {"failed_check": "candidate_source_bounded_safe_tree", "scan_reason": "hardlink_forbidden"}),
    ]
    for variant_name, kind, executor, expected, notes, target in matrix:
        started = time.monotonic()
        result = verifier.verify_candidate(Path(args.ownership_plan), variants[variant_name])
        duration = time.monotonic() - started
        observed = result["verdict"]
        targeted = target_observed(result, target)
        passed = observed == expected and targeted
        evidence_ref = write_evidence(
            evidence_dir, evidence_ref_prefix, variant_name, result
        )
        tests.append(test_record(
            test_id=variant_name,
            kind=kind,
            executor=executor,
            command=f"verifier.verify_candidate(/runtime/runtime_ownership_plan.json, /runtime/candidates/{variant_name})",
            passed=passed,
            expected=expected,
            observed=observed,
            duration=duration,
            initial_hash=initial_hash,
            final_hash=result["candidate_source_sha256"],
            evidence_ref=evidence_ref,
            notes=f"{notes} 目标断言={json.dumps(target, ensure_ascii=False, sort_keys=True)}；命中={targeted}。",
        ))

    by_kind: dict[str, dict[str, int]] = {}
    for kind in ("reset", "positive", "minimal_negative", "side_effect"):
        selected = [item for item in tests if item["kind"] == kind]
        by_kind[kind] = {
            "total": len(selected),
            "passed": sum(item["status"] == "passed" for item in selected),
            "failed": sum(item["status"] == "failed" for item in selected),
            "invalid": sum(item["status"] == "invalid" for item in selected),
        }
    failed = sum(item["status"] == "failed" for item in tests)
    invalid = sum(item["status"] == "invalid" for item in tests)
    report = {
        "schema_version": "nami_work_env_validation_report_v1",
        "run_id": args.run_id,
        "task_id": "case_10",
        "case_version": args.case_version,
        "started_at": started_at,
        "finished_at": utc_now(),
        "status": "invalid" if invalid else ("failed" if failed else "passed"),
        "environment": {
            "host_id": plan["hostname"],
            "image_digest": contract["image"]["digest"],
            "verifier_sha256": verifier.file_sha256(VERIFIER_PATH),
        },
        "tests": tests,
        "summary": {
            "total": len(tests),
            "passed": sum(item["status"] == "passed" for item in tests),
            "failed": failed,
            "invalid": invalid,
            "by_kind": by_kind,
        },
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
