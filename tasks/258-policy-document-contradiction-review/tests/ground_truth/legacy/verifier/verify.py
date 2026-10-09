#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
from pathlib import Path
from typing import Any


CASE_DIR = Path(__file__).resolve().parents[1]
GROUND_TRUTH = CASE_DIR / "oracle" / "ground_truth.json"
WORKSPACE_MANIFEST = CASE_DIR / "environment" / "workspace_manifest.json"
EXPECTED_FILES = {
    "TASK.md",
    "input/A01_采购管理办法_v3.2.md",
    "input/A02_费用报销细则_v2.0.md",
    "input/A03_信息安全控制标准_v4.0.md",
    "input/A04_远程办公实施细则_v1.3.md",
    "input/A05_制度版本与引用目录_2026Q2.md",
    "output/review_report.json",
}
EXPECTED_DIRECTORIES = {"input", "output"}
MAX_REPORT_BYTES = 256 * 1024


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(checks: list[dict[str, Any]], check_id: str, passed: bool, detail: str) -> None:
    checks.append({"check_id": check_id, "passed": bool(passed), "detail": detail})


def regular_tree(workspace: Path) -> tuple[set[str], set[str], bool]:
    files: set[str] = set()
    directories: set[str] = set()
    safe = True
    for path in workspace.rglob("*"):
        relative = path.relative_to(workspace).as_posix()
        if path.is_symlink():
            safe = False
            continue
        mode = path.lstat().st_mode
        if stat.S_ISREG(mode):
            files.add(relative)
        elif stat.S_ISDIR(mode):
            directories.add(relative)
        else:
            safe = False
    return files, directories, safe


def structurally_valid(report: Any, input_paths: list[str]) -> bool:
    if not isinstance(report, dict) or set(report) != {"schema_version", "review_scope", "summary", "findings"}:
        return False
    if report.get("schema_version") != "multi_policy_review_report_v1":
        return False
    scope = report.get("review_scope")
    if not isinstance(scope, dict) or set(scope) != {"files_reviewed", "scope_statement"}:
        return False
    files_reviewed = scope.get("files_reviewed")
    scope_statement = scope.get("scope_statement")
    if (
        not isinstance(files_reviewed, list)
        or not all(isinstance(item, str) for item in files_reviewed)
        or sorted(files_reviewed) != sorted(input_paths)
        or not isinstance(scope_statement, str)
        or not 8 <= len(scope_statement.strip()) <= 1000
    ):
        return False
    summary = report.get("summary")
    if not isinstance(summary, dict) or set(summary) != {"total_findings", "high", "medium", "low", "conclusion"}:
        return False
    if not isinstance(summary.get("conclusion"), str) or not 8 <= len(summary["conclusion"].strip()) <= 1000:
        return False
    for key in ("total_findings", "high", "medium", "low"):
        value = summary.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return False
    findings = report.get("findings")
    if not isinstance(findings, list) or not 1 <= len(findings) <= 32:
        return False
    ids: set[str] = set()
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != {"finding_id", "issue_type", "severity", "title", "evidence", "judgment", "recommendation"}:
            return False
        if finding.get("issue_type") not in {"fact_conflict", "version_mismatch", "reference_error"}:
            return False
        if finding.get("severity") not in {"high", "medium", "low"}:
            return False
        finding_id = finding.get("finding_id")
        if not isinstance(finding_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,31}", finding_id) or finding_id in ids:
            return False
        ids.add(finding_id)
        if not all(
            isinstance(finding.get(key), str)
            and 4 <= len(finding[key].strip()) <= 1000
            for key in ("title", "judgment")
        ):
            return False
        evidence = finding.get("evidence")
        if not isinstance(evidence, list) or len(evidence) < 2:
            return False
        for item in evidence:
            if not isinstance(item, dict) or set(item) != {"file", "section", "quote"}:
                return False
            if not all(
                isinstance(item.get(key), str)
                and item[key].strip()
                and len(item[key]) <= 2000
                for key in ("file", "section", "quote")
            ):
                return False
        recommendation = finding.get("recommendation")
        if not isinstance(recommendation, dict) or set(recommendation) != {"action", "target_file", "target_section", "replacement_text"}:
            return False
        if not all(
            isinstance(recommendation.get(key), str)
            and recommendation[key].strip()
            and len(recommendation[key]) <= 2000
            for key in recommendation
        ):
            return False
    return True


def evidence_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (str(item.get("file")), str(item.get("section")), str(item.get("quote")))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    workspace = Path(args.workspace).resolve(strict=True)
    result_path = Path(args.result)
    checks: list[dict[str, Any]] = []
    evidence: dict[str, Any] = {}

    files, directories, safe_nodes = regular_tree(workspace)
    check(checks, "workspace_no_symlinks", safe_nodes, "工作区不得包含符号链接或特殊文件")
    check(checks, "workspace_exact_files", files == EXPECTED_FILES, f"observed_regular_files={len(files)}")
    check(
        checks,
        "workspace_exact_directories",
        directories == EXPECTED_DIRECTORIES,
        f"observed_directories={sorted(directories)}",
    )

    manifest = json.loads(WORKSPACE_MANIFEST.read_text(encoding="utf-8"))
    input_ok = True
    for item in manifest["files"]:
        path = workspace / item["path"]
        if not path.is_file() or path.is_symlink() or sha256(path) != item["sha256"]:
            input_ok = False
    check(checks, "input_integrity", input_ok, "所有固定输入必须与初态清单一致")

    report_path = workspace / "output" / "review_report.json"
    report_size_ok = (
        report_path.is_file()
        and not report_path.is_symlink()
        and 0 < report_path.stat().st_size <= MAX_REPORT_BYTES
    )
    check(checks, "report_size", report_size_ok, "报告必须是非空且不超过 256 KiB 的普通文件")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_size_ok else None
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
        report = None
    input_paths = [item["path"] for item in manifest["files"] if item["path"].startswith("input/")]
    structure_ok = structurally_valid(report, input_paths)
    check(checks, "report_structure", structure_ok, "报告必须满足固定 JSON 合同")

    truth = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    expected = truth["expected_findings"]
    findings = report.get("findings", []) if isinstance(report, dict) and isinstance(report.get("findings"), list) else []
    matched_indices: set[int] = set()
    recall_ok = structure_ok
    evidence_ok = structure_ok
    severity_ok = structure_ok
    recommendation_ok = structure_ok
    match_rows: list[dict[str, Any]] = []
    for target in expected:
        target_evidence = {evidence_key(item) for item in target["evidence"]}
        matches: list[tuple[int, dict[str, Any]]] = []
        for index, finding in enumerate(findings):
            if not isinstance(finding, dict) or finding.get("issue_type") != target["issue_type"]:
                continue
            observed_evidence = {evidence_key(item) for item in finding.get("evidence", []) if isinstance(item, dict)}
            if target_evidence == observed_evidence:
                matches.append((index, finding))
        if len(matches) != 1:
            recall_ok = False
            evidence_ok = False
            match_rows.append({"ground_truth_id": target["ground_truth_id"], "match_count": len(matches)})
            continue
        index, finding = matches[0]
        matched_indices.add(index)
        if finding.get("severity") != target["severity"]:
            severity_ok = False
        rec = finding.get("recommendation", {})
        target_rec = target["recommendation"]
        if rec.get("target_file") != target_rec["target_file"] or rec.get("target_section") != target_rec["target_section"]:
            recommendation_ok = False
        combined = f"{rec.get('action', '')} {rec.get('replacement_text', '')}"
        if any(term not in combined for term in target_rec["required_terms"]):
            recommendation_ok = False
        match_rows.append({"ground_truth_id": target["ground_truth_id"], "match_count": 1, "finding_id": finding.get("finding_id")})

    precision_ok = structure_ok and len(findings) == len(expected) and matched_indices == set(range(len(findings)))
    distractor_quotes = {quote for item in truth["semantic_distractors"] for quote in item["quotes"]}
    distractor_false_positive = False
    for index, finding in enumerate(findings):
        if index in matched_indices or not isinstance(finding, dict):
            continue
        observed_quotes = {str(item.get("quote")) for item in finding.get("evidence", []) if isinstance(item, dict)}
        if observed_quotes & distractor_quotes:
            distractor_false_positive = True
    precision_ok = precision_ok and not distractor_false_positive
    check(checks, "contradiction_recall", recall_ok, f"matched={len(matched_indices)}/{len(expected)}")
    check(checks, "evidence_localization", evidence_ok, "每项问题必须给出精确文件、章节和原文")
    check(checks, "false_positive_control", precision_ok, "不得报告额外问题或把近似措辞误报为冲突")
    check(checks, "severity_accuracy", severity_ok, "严重性必须与确定性规则一致")
    check(checks, "actionable_recommendations", recommendation_ok, "建议必须指向待修订文件、章节并包含可采用文本")

    summary_ok = False
    if structure_ok:
        summary = report["summary"]
        counts = {level: sum(item.get("severity") == level for item in findings) for level in ("high", "medium", "low")}
        summary_ok = summary["total_findings"] == len(findings) and all(summary[level] == counts[level] for level in counts)
    check(checks, "summary_consistency", summary_ok, "汇总计数必须由 findings 推导")

    passed = all(item["passed"] for item in checks)
    evidence["finding_matches"] = match_rows
    payload = {
        "schema_version": "case04_verifier_result_v1",
        "task_id": "case_04",
        "verdict": "accept" if passed else "reject",
        "checks": checks,
        "metrics": {
            "expected_findings": len(expected),
            "reported_findings": len(findings),
            "matched_findings": len(matched_indices),
            "passed_checks": sum(item["passed"] for item in checks),
            "total_checks": len(checks)
        },
        "evidence": evidence
    }
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": payload["verdict"], "passed_checks": payload["metrics"]["passed_checks"], "total_checks": len(checks)}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
