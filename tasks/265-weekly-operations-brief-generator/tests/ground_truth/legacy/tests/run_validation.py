#!/usr/bin/env python3
"""case_11 版本 2.2 的正式正例、最小反例和沙箱对抗验证。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CASE_ROOT = Path(__file__).resolve().parents[1]
RESET = CASE_ROOT / "environment/reset.py"
CONTROLLER = CASE_ROOT / "environment/sandbox_controller.py"
CONTRACT = CASE_ROOT / "environment/sandbox_contract.json"
EVALUATOR = CASE_ROOT / "verifier/evaluate_submission.py"
TERMINAL_VERIFIER = CASE_ROOT / "verifier/verify_outputs.py"
VARIANT_MANIFEST = CASE_ROOT / "tests/hidden/variant_manifest.json"
ORACLE = CASE_ROOT / "oracle/reference_generator.py"
SEMANTIC_REGRESSION = CASE_ROOT / "tests/test_semantic_verifier.py"
REFERENCE = CASE_ROOT / "oracle/reference_output"
ZERO_HASH = "0" * 64


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(command: list[str], *, timeout: int = 900) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return ZERO_HASH
    for current, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in sorted(dirnames):
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            status = path.lstat()
            digest.update(f"d:{stat.S_IMODE(status.st_mode):o}:{relative}\0".encode("utf-8"))
        for name in sorted(filenames):
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            status = path.lstat()
            digest.update(f"f:{stat.S_IMODE(status.st_mode):o}:{relative}:{status.st_size}\0".encode("utf-8"))
            if stat.S_ISREG(status.st_mode) and not path.is_symlink():
                with path.open("rb") as handle:
                    for block in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(block)
            digest.update(b"\0")
    return digest.hexdigest()


def write_new_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
    try:
        payload = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def mutate_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError("变异锚点不唯一")
    return source.replace(old, new, 1)


def hardcoded_source() -> str:
    summary = repr((REFERENCE / "summary.json").read_bytes())
    brief = repr((REFERENCE / "weekly_brief.md").read_bytes())
    return f"""#!/usr/bin/env python3
import argparse
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('--input-csv'); p.add_argument('--definitions'); p.add_argument('--template'); p.add_argument('--output-dir'); a=p.parse_args()
out=Path(a.output_dir); out.mkdir(exist_ok=True)
(out/'summary.json').write_bytes({summary})
(out/'weekly_brief.md').write_bytes({brief})
"""


class Suite:
    def __init__(self, plan_path: Path, report_path: Path, evidence_dir: Path, run_id: str):
        self.plan_path = plan_path.resolve(strict=True)
        self.plan = json.loads(self.plan_path.read_text(encoding="utf-8"))
        self.attempts_root = Path(self.plan["attempts_root"]).resolve(strict=True)
        self.remote_evidence = Path(self.plan["evidence_root"]).resolve(strict=True)
        self.report_path = report_path.resolve()
        if self.report_path.exists() or self.report_path.is_symlink():
            raise RuntimeError("正式报告不得覆盖")
        self.evidence_dir = evidence_dir.resolve()
        self.evidence_dir.mkdir(parents=True)
        self.run_id = run_id
        self.tests: list[dict[str, Any]] = []

    def actual_id(self, logical: str) -> str:
        digest = hashlib.sha256(f"{self.run_id}:{logical}".encode("utf-8")).hexdigest()[:12]
        slug = re.sub(r"[^a-z0-9]+", "-", logical.lower()).strip("-")[:34]
        return f"v2-{digest}-{slug}"

    def relative(self, path: Path) -> str:
        return path.resolve().relative_to(CASE_ROOT.resolve()).as_posix()

    def reset(self, logical: str, variant: str = "primary") -> tuple[str, Path, dict[str, Any]]:
        workspace_id = self.actual_id(logical)
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
            timeout=30,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"reset 失败：{logical}:{completed.stderr[-200:]}")
        value = json.loads(completed.stdout)
        return workspace_id, (self.attempts_root / workspace_id).resolve(strict=True), value

    @staticmethod
    def install(workspace: Path, source: str) -> None:
        path = workspace / "submission/generate_brief.py"
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        try:
            os.write(descriptor, source.encode("utf-8"))
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def seed_expected_outputs(workspace: Path) -> None:
        for name in ("summary.json", "weekly_brief.md"):
            shutil.copyfile(REFERENCE / name, workspace / "output" / name)

    def add_test(
        self,
        *,
        test_id: str,
        kind: str,
        executor: str,
        expected: str,
        observed: str,
        exit_code: int | None,
        started: float,
        initial_hash: str,
        final_hash: str,
        evidence_refs: list[str],
        notes: str,
    ) -> None:
        self.tests.append(
            {
                "test_id": test_id,
                "kind": kind,
                "executor": executor,
                "status": "passed" if expected == observed else "failed",
                "expected_verdict": expected,
                "observed_verdict": observed,
                "exit_code": 0 if expected == observed else exit_code,
                "duration_seconds": round(time.monotonic() - started, 6),
                "initial_state_sha256": initial_hash,
                "final_state_sha256": final_hash,
                "evidence_refs": evidence_refs,
                "notes": notes,
            }
        )

    def reset_test(self, test_id: str) -> str:
        started = time.monotonic()
        _, workspace, value = self.reset(test_id)
        evidence = self.evidence_dir / f"{test_id}.json"
        write_new_json(evidence, value)
        initial = value["initial_state_sha256"]
        self.add_test(
            test_id=test_id,
            kind="reset",
            executor="reset",
            expected="accept",
            observed="accept",
            exit_code=0,
            started=started,
            initial_hash=initial,
            final_hash=initial,
            evidence_refs=[self.relative(evidence)],
            notes="reset 返回版本化初态哈希、输入哈希和外部 baseline；两次独立结果在套件末端比较。",
        )
        return initial

    def evaluator_test(self, test_id: str, kind: str, source: str, expected: str) -> None:
        started = time.monotonic()
        _, workspace, reset_value = self.reset(f"submission-{test_id}")
        self.install(workspace, source)
        self.seed_expected_outputs(workspace)
        evaluation_id = self.actual_id(f"evaluation-{test_id}")
        result_source = self.remote_evidence / "evaluations" / evaluation_id / "result.json"
        completed = run(
            [
                sys.executable,
                EVALUATOR.as_posix(),
                "--plan",
                self.plan_path.as_posix(),
                "--submission-workspace",
                workspace.as_posix(),
                "--evaluation-id",
                evaluation_id,
                "--result",
                result_source.as_posix(),
            ],
            timeout=900,
        )
        if not result_source.is_file():
            result: dict[str, Any] = {"status": "invalid", "missing_result": True, "stderr": completed.stderr[-300:]}
        else:
            result = json.loads(result_source.read_text(encoding="utf-8"))
        persistent = self.evidence_dir / test_id
        if persistent.exists():
            raise RuntimeError("验收证据目标已存在")
        source_dir = result_source.parent
        if source_dir.is_dir():
            shutil.copytree(source_dir, persistent)
        else:
            persistent.mkdir()
            write_new_json(persistent / "missing_result.json", result)
        status = result.get("status")
        observed = "accept" if status == "passed" else "reject" if status == "failed" else "not_observed"
        self.add_test(
            test_id=test_id,
            kind=kind,
            executor="oracle" if kind == "positive" else "verifier_test",
            expected=expected,
            observed=observed,
            exit_code=completed.returncode,
            started=started,
            initial_hash=reset_value["initial_state_sha256"],
            final_hash=tree_hash(workspace),
            evidence_refs=[self.relative(persistent / "result.json") if (persistent / "result.json").exists() else self.relative(persistent / "missing_result.json")],
            notes=f"真实候选验收聚合结果={status}；进程退出码={completed.returncode}。",
        )

    def direct_sandbox_test(self, test_id: str, source: str, predicate: str) -> None:
        started = time.monotonic()
        workspace_id, workspace, reset_value = self.reset(f"sandbox-{test_id}")
        self.install(workspace, source)
        invocation_id = self.actual_id(f"invocation-{test_id}")
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
            timeout=60,
        )
        source_result = self.remote_evidence / f"{invocation_id}.sandbox.json"
        result = json.loads(source_result.read_text(encoding="utf-8")) if source_result.is_file() else {"missing_result": True}
        evidence = self.evidence_dir / f"{test_id}.sandbox.json"
        write_new_json(evidence, result)
        container_id = result.get("container_id")
        container_name = result.get("container_name")
        completed_contract = (
            completed.returncode == 0
            and result.get("controller_status") == "passed"
            and result.get("creation_predeclared") is True
            and result.get("started_container") is True
            and result.get("timed_out") is False
            and result.get("quota_exceeded") is False
            and result.get("entry_limit_exceeded") is False
            and result.get("single_file_limit_exceeded") is False
            and result.get("unsafe_entry_detected") is False
            and result.get("log_limit_exceeded") is False
            and result.get("inventory_scan_failed") is False
            and not result.get("preflight_contract_errors")
            and not result.get("postflight_contract_errors")
            and result.get("controller_error") is None
            and isinstance(container_id, str)
            and re.fullmatch(r"[0-9a-f]{64}", container_id) is not None
            and isinstance(container_name, str)
            and bool(container_name)
        )
        if predicate == "candidate_nonzero":
            rejected = (
                completed_contract
                and isinstance(result.get("candidate_exit_code"), int)
                and result["candidate_exit_code"] != 0
            )
        elif predicate == "quota":
            rejected = result.get("quota_exceeded") is True and result.get("controller_status") == "failed" and not result.get("postflight_contract_errors")
        elif predicate == "log_limit":
            rejected = result.get("log_limit_exceeded") is True and result.get("controller_status") == "failed" and len(result.get("stdout_tail", "").encode("utf-8")) <= 262144
        elif predicate == "inventory_scan":
            rejected = result.get("inventory_scan_failed") is True and result.get("controller_status") == "failed" and not result.get("postflight_contract_errors")
        elif predicate == "inventory_scan_or_quota":
            rejected = (
                (result.get("inventory_scan_failed") is True or result.get("quota_exceeded") is True)
                and result.get("controller_status") == "failed"
                and not result.get("postflight_contract_errors")
            )
        elif predicate == "timeout":
            rejected = result.get("timed_out") is True and result.get("controller_status") == "passed" and not result.get("postflight_contract_errors")
        elif predicate == "quiescent_no_outputs":
            rejected = result.get("candidate_exit_code") == 0 and result.get("controller_status") == "passed" and not any((workspace / "output").iterdir()) and not result.get("postflight_contract_errors")
        else:
            raise RuntimeError("未知 predicate")
        self.add_test(
            test_id=test_id,
            kind="side_effect",
            executor="verifier_test",
            expected="reject",
            observed="reject" if rejected else "accept",
            exit_code=result.get("candidate_exit_code") if isinstance(result.get("candidate_exit_code"), int) else completed.returncode,
            started=started,
            initial_hash=reset_value["initial_state_sha256"],
            final_hash=tree_hash(workspace),
            evidence_refs=[self.relative(evidence)],
            notes=f"沙箱对抗谓词={predicate}；控制器退出码={completed.returncode}。",
        )

    def semantic_regression_test(self, initial_hash: str) -> None:
        started = time.monotonic()
        completed = run([sys.executable, "-B", SEMANTIC_REGRESSION.as_posix()], timeout=30)
        evidence = self.evidence_dir / "semantic_verifier_regression.json"
        write_new_json(
            evidence,
            {
                "return_code": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            },
        )
        self.add_test(
            test_id="semantic_verifier_regression",
            kind="minimal_negative",
            executor="verifier_test",
            expected="reject",
            observed="reject" if completed.returncode == 0 else "accept",
            exit_code=completed.returncode,
            started=started,
            initial_hash=initial_hash,
            final_hash=initial_hash,
            evidence_refs=[self.relative(evidence)],
            notes="不启动容器，覆盖符号混淆、拼接表格、否定风险/动作、额外章节和宽松日期误收。",
        )

    def finish(self, started_at: str) -> dict[str, Any]:
        by_kind: dict[str, dict[str, int]] = {}
        for kind in ("reset", "positive", "minimal_negative", "side_effect"):
            subset = [item for item in self.tests if item["kind"] == kind]
            by_kind[kind] = {
                "total": len(subset),
                "passed": sum(item["status"] == "passed" for item in subset),
                "failed": sum(item["status"] == "failed" for item in subset),
                "invalid": sum(item["status"] == "invalid" for item in subset),
            }
        report = {
            "schema_version": "nami_work_env_validation_report_v1",
            "run_id": self.run_id,
            "task_id": "case_11",
            "case_version": "2.2.0",
            "started_at": started_at,
            "finished_at": now(),
            "status": "passed" if all(item["status"] == "passed" for item in self.tests) else "failed",
            "environment": {
                "host_id": self.plan["host_alias"],
                "image_digest": self.plan["image_digest"],
                "verifier_sha256": file_hash(EVALUATOR),
                "sandbox_controller_sha256": file_hash(CONTROLLER),
                "sandbox_contract_sha256": file_hash(CONTRACT),
                "terminal_verifier_sha256": file_hash(TERMINAL_VERIFIER),
                "fixture_variant_manifest_sha256": file_hash(VARIANT_MANIFEST),
                "reset_sha256": file_hash(RESET),
                "validation_driver_sha256": file_hash(Path(__file__).resolve()),
                "oracle_sha256": file_hash(ORACLE),
                "semantic_regression_sha256": file_hash(SEMANTIC_REGRESSION),
            },
            "tests": self.tests,
            "summary": {
                "total": len(self.tests),
                "passed": sum(item["status"] == "passed" for item in self.tests),
                "failed": sum(item["status"] == "failed" for item in self.tests),
                "invalid": sum(item["status"] == "invalid" for item in self.tests),
                "by_kind": by_kind,
            },
        }
        write_new_json(self.report_path, report)
        return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--run-id", default="case11_root_final_v22")
    args = parser.parse_args()
    started_at = now()
    suite = Suite(args.plan, args.report, args.evidence_dir, args.run_id)
    reset_a = suite.reset_test("reset_consistency_a")
    reset_b = suite.reset_test("reset_consistency_b")
    if reset_a != reset_b:
        suite.tests[-1]["status"] = "failed"
        suite.tests[-1]["observed_verdict"] = "reject"
        suite.tests[-1]["notes"] = "两次独立 reset 的初态哈希不一致。"

    oracle_source = ORACLE.read_text(encoding="utf-8")
    suite.evaluator_test("oracle_full_evaluation_a", "positive", oracle_source, "accept")
    suite.evaluator_test("oracle_full_evaluation_b", "positive", oracle_source, "accept")
    suite.semantic_regression_test(reset_a)

    suite.evaluator_test("reject_hardcoded_primary", "minimal_negative", hardcoded_source(), "reject")
    suite.evaluator_test("reject_prewritten_outputs_dummy_script", "minimal_negative", "#!/usr/bin/env python3\nraise SystemExit(3)\n", "reject")
    wrong_metric = mutate_once(
        oracle_source,
        '"refund_rate_pct": pct(current["refund_cents"], current["revenue_cents"]),',
        '"refund_rate_pct": pct(current["refund_cents"], current["visits"]),',
    )
    suite.evaluator_test("reject_wrong_metric", "minimal_negative", wrong_metric, "reject")
    non_idempotent = mutate_once(
        oracle_source,
        "    atomic_outputs(args.output_dir, summary_bytes, brief.encode(\"utf-8\"))",
        "    existed = (args.output_dir / 'weekly_brief.md').exists()\n    atomic_outputs(args.output_dir, summary_bytes, brief.encode(\"utf-8\"))\n    if existed:\n        (args.output_dir / 'weekly_brief.md').write_text((args.output_dir / 'weekly_brief.md').read_text(encoding='utf-8') + '<!-- second-run -->\\n', encoding='utf-8')",
    )
    suite.evaluator_test("reject_non_idempotent", "minimal_negative", non_idempotent, "reject")
    swallowed_invalid = mutate_once(oracle_source, "        return 2", "        return 0")
    suite.evaluator_test("reject_swallowed_invalid", "minimal_negative", swallowed_invalid, "reject")
    invalid_timeout = mutate_once(
        oracle_source,
        "        return 2",
        "        import time\n        time.sleep(60)\n        return 2",
    )
    suite.evaluator_test("reject_invalid_timeout", "minimal_negative", invalid_timeout, "reject")
    corrupt_existing_on_invalid = mutate_once(
        oracle_source,
        "        return 2",
        "        args = parse_args()\n        summary = args.output_dir / 'summary.json'\n        brief = args.output_dir / 'weekly_brief.md'\n        if summary.exists():\n            summary.unlink()\n        if brief.exists():\n            brief.write_bytes(b'corrupted-last-known-good')\n        return 2",
    )
    suite.evaluator_test(
        "reject_invalid_mutates_existing_outputs",
        "minimal_negative",
        corrupt_existing_on_invalid,
        "reject",
    )

    cache_mutant = mutate_once(
        oracle_source,
        "        run(parse_args())",
        "        args = parse_args()\n        run(args)\n        Path('/workspace/cache').mkdir()",
    )
    suite.direct_sandbox_test("reject_cache_write", cache_mutant, "candidate_nonzero")
    input_mutant = mutate_once(
        oracle_source,
        "        run(parse_args())",
        "        args = parse_args()\n        run(args)\n        args.input_csv.write_bytes(args.input_csv.read_bytes())",
    )
    suite.direct_sandbox_test("reject_same_byte_input_rewrite", input_mutant, "candidate_nonzero")
    hardlink_mutant = mutate_once(
        oracle_source,
        "        run(parse_args())",
        "        args = parse_args()\n        run(args)\n        os.link(args.input_csv, args.output_dir / 'input-link')",
    )
    suite.direct_sandbox_test("reject_input_hardlink", hardlink_mutant, "candidate_nonzero")
    quota_source = """#!/usr/bin/env python3
import argparse
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('--input-csv'); p.add_argument('--definitions'); p.add_argument('--template'); p.add_argument('--output-dir'); a=p.parse_args()
out=Path(a.output_dir)
for i in range(100):
    (out/f'chunk-{i:03d}.bin').write_bytes(b'x' * 1048576)
"""
    suite.direct_sandbox_test("reject_total_workspace_quota", quota_source, "quota")
    flood_source = "#!/usr/bin/env python3\nimport os\nos.write(1, b'x' * 1048576)\n"
    suite.direct_sandbox_test("reject_stdout_flood", flood_source, "log_limit")
    unreadable_source = """#!/usr/bin/env python3
import argparse
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('--input-csv'); p.add_argument('--definitions'); p.add_argument('--template'); p.add_argument('--output-dir'); a=p.parse_args()
private=Path(a.output_dir)/'private'; private.mkdir(mode=0o700)
for i in range(100):
    (private/f'chunk-{i:03d}.bin').write_bytes(b'x' * 1048576)
"""
    suite.direct_sandbox_test("reject_unreadable_quota_evasion", unreadable_source, "inventory_scan_or_quota")
    invalid_utf8_timeout = "#!/usr/bin/env python3\nimport os, time\nos.write(2, b'\\xff' * 4096)\ntime.sleep(60)\n"
    suite.direct_sandbox_test("reject_invalid_utf8_timeout", invalid_utf8_timeout, "timeout")
    background = "#!/usr/bin/env python3\nimport subprocess\nsubprocess.Popen(['/usr/local/bin/python3','-c','import time;time.sleep(60)'])\n"
    suite.direct_sandbox_test("reject_background_process_without_delivery", background, "quiescent_no_outputs")

    report = suite.finish(started_at)
    print(json.dumps({"status": report["status"], **report["summary"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
