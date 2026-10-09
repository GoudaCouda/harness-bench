#!/usr/bin/env python3
"""Deterministic verifier for the case 13 synthetic research report."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path


REPORT_NAME = "养老行业研究报告.md"
REPORT_TITLE = "# 岚州市养老服务供需与行动建议"
VALID_SOURCES = {f"S{i:02d}" for i in range(1, 8)}
EXPECTED_METRICS = {
    "M01": ("336000", "人", {"S01"}, ("2025", "规划基线")),
    "M02": ("370440", "人", {"S01"}, ("2027", "规划预测")),
    "M03": ("5.0", "%", {"S01"}, ("370440", "336000")),
    "M04": ("80640", "个服务位", {"S01", "S02"}, ("24.0%", "规划服务量")),
    "M05": ("31640", "个服务位", {"S01", "S02", "S03"}, ("80640", "49000")),
    "M06": ("141120", "人次/年", {"S01", "S02"}, ("42.0%", "规划服务量")),
    "M07": ("13120", "人次/年", {"S01", "S02", "S03"}, ("141120", "128000")),
    "M08": ("30240", "张床位", {"S01", "S02"}, ("9.0%", "规划服务量")),
    "M09": ("2440", "张床位", {"S01", "S02", "S03"}, ("30240", "27800")),
    "M10": ("1.5", "年", {"S06", "S07"}, ("180", "120", "简单回收")),
    "M11": ("363860000", "元/年", {"S01", "S02", "S03", "S05"}, ("31640", "11500")),
    "M12": ("94464000", "元/年", {"S01", "S02", "S03", "S05"}, ("13120", "7200")),
    "M13": ("102480000", "元/年", {"S01", "S02", "S03", "S05"}, ("2440", "42000")),
}
EXPECTED_CLAIMS = {
    "C01": ({"S01"}, ("老龄人口", "规划"), ("规划", "预测")),
    "C02": ({"S01", "S02", "S03"}, ("社区", "缺口"), ("规划情景",)),
    "C03": ({"S01", "S02", "S03"}, ("居家", "缺口"), ("能力",)),
    "C04": ({"S01", "S02", "S03"}, ("机构", "缺口"), ("偏好",)),
    "C05": ({"S06", "S07"}, ("1.5", "回收"), ("因果", "成本")),
    "C06": ({"S04"}, ("社区", "培训"), ("审批",)),
}
EXPECTED_RECOMMENDATIONS = {
    "R01": ("P0", {"S02", "S03", "S04", "S05"}, ("社区", "服务位"), ("审批", "量级")),
    "R02": ("P0", {"S02", "S03", "S04", "S05"}, ("居家", "培训"), ("资格", "量级")),
    "R03": ("P1", {"S06", "S07"}, ("试点",), ("上限", "测量")),
}
EXPECTED_BIBLIOGRAPHY = {
    "S01": ("岚州市老龄人口规划基线（2025年版）", "中文"),
    "S02": ("岚州市养老服务偏好调查（加权结果）", "中文"),
    "S03": ("岚州市合格养老服务供给登记表", "中文"),
    "S04": ("岚州市银龄服务专项资金使用规则（2025年试行）", "中文"),
    "S05": ("岚州市养老服务规划单价说明", "中文"),
    "S06": ("Community Scheduling Pilot Note", "English"),
    "S07": ("Independent Cost Review of the Scheduling Pilot", "English"),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_tree_entries(
    root: Path,
    *,
    max_entries: int = 64,
    max_total_bytes: int = 2 * 1024 * 1024,
) -> list[tuple[str, str, Path, os.stat_result]]:
    """Return a bounded, globally sorted tree without following links."""
    if root.is_symlink() or not root.is_dir():
        raise ValueError("tree_root_not_regular_directory")
    pending = [root]
    result: list[tuple[str, str, Path, os.stat_result]] = []
    total_bytes = 0
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda item: item.name)
        except OSError as exc:
            raise ValueError(f"tree_scan_error:{directory.relative_to(root)}:{type(exc).__name__}") from exc
        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(root).as_posix()
            try:
                metadata = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise ValueError(f"tree_stat_error:{relative}:{type(exc).__name__}") from exc
            if stat.S_ISLNK(metadata.st_mode):
                raise ValueError(f"tree_symlink:{relative}")
            if stat.S_ISDIR(metadata.st_mode):
                kind = "D"
                pending.append(path)
            elif stat.S_ISREG(metadata.st_mode):
                kind = "F"
                total_bytes += metadata.st_size
                if total_bytes > max_total_bytes:
                    raise ValueError("tree_total_bytes_exceeded")
            else:
                raise ValueError(f"tree_special:{relative}")
            result.append((kind, relative, path, metadata))
            if len(result) > max_entries:
                raise ValueError("tree_entry_count_exceeded")
    return sorted(result, key=lambda item: item[1])


def tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for kind, rel, path, _ in safe_tree_entries(root):
        if kind == "D":
            digest.update(f"D\0{rel}\0".encode())
        else:
            digest.update(f"F\0{rel}\0{sha256_file(path)}\0".encode())
    return digest.hexdigest()


def citations(text: str) -> set[str]:
    return set(re.findall(r"\[(S\d{2})\]", text))


def compact_number(value: str) -> str:
    return value.replace(",", "").replace(" ", "").strip()


def section(text: str, heading: str, next_heading: str | None) -> str:
    marker = f"## {heading}\n"
    if text.count(marker) != 1:
        raise ValueError(f"missing_or_duplicate_section:{heading}")
    body = text.split(marker, 1)[1]
    if next_heading is not None:
        next_marker = f"## {next_heading}\n"
        if next_marker not in body:
            raise ValueError(f"section_order:{heading}")
        body = body.split(next_marker, 1)[0]
    return body.strip()


def parse_table(body: str, columns: int) -> list[list[str]]:
    lines = [line.strip() for line in body.splitlines() if line.strip().startswith("|")]
    if len(lines) < 3:
        raise ValueError("table_missing")
    rows: list[list[str]] = []
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != columns:
            raise ValueError("table_column_count")
        rows.append(cells)
    return rows


def verify_workspace(workspace: Path, case_root: Path) -> tuple[list[dict[str, object]], list[str]]:
    checks: list[dict[str, object]] = []
    violations: list[str] = []

    def add(check_id: str, passed: bool, evidence: str) -> None:
        checks.append({"check_id": check_id, "passed": passed, "evidence": evidence})
        if not passed:
            violations.append(f"{check_id}:{evidence}")

    seed = json.loads((case_root / "environment/workspace_seed_manifest.json").read_text())
    expected_files = {item["path"]: item["sha256"] for item in seed["files"]}
    try:
        workspace_entries = safe_tree_entries(workspace)
        root_entries = {relative for _, relative, _, _ in workspace_entries if "/" not in relative}
        workspace_ok = root_entries == {"input", "output"}
        add("workspace_scope", workspace_ok, f"entries={sorted(root_entries)}")
        add(
            "workspace_tree_bounds",
            True,
            f"entries={len(workspace_entries)}",
        )
    except (OSError, ValueError) as exc:
        add("workspace_scope", False, str(exc))
        return checks, violations

    input_root = workspace / "input"
    output_root = workspace / "output"
    try:
        input_entries = safe_tree_entries(input_root, max_entries=32, max_total_bytes=512 * 1024)
        actual_files = {
            relative: sha256_file(path)
            for kind, relative, path, _ in input_entries
            if kind == "F"
        }
        input_ok = actual_files == expected_files and tree_sha256(input_root) == seed["input_tree_sha256"]
        mode_errors = [
            f"{relative}:{oct(stat.S_IMODE(metadata.st_mode))}"
            for kind, relative, _, metadata in input_entries
            if (kind == "F" and stat.S_IMODE(metadata.st_mode) != 0o444)
            or (kind == "D" and stat.S_IMODE(metadata.st_mode) != 0o555)
        ]
        input_root_mode = stat.S_IMODE(input_root.stat(follow_symlinks=False).st_mode)
        if input_root_mode != 0o555:
            mode_errors.append(f".:{oct(input_root_mode)}")
        add("protected_input_integrity", input_ok, f"files={len(actual_files)}")
        add("protected_input_modes", not mode_errors, f"errors={mode_errors}")
    except (OSError, ValueError) as exc:
        add("protected_input_integrity", False, f"candidate_input_error:{type(exc).__name__}:{exc}")
        return checks, violations

    try:
        output_tree = safe_tree_entries(output_root, max_entries=2, max_total_bytes=128 * 1024)
    except (OSError, ValueError) as exc:
        add("deliverable_scope", False, f"candidate_output_error:{type(exc).__name__}:{exc}")
        return checks, violations
    report = output_root / REPORT_NAME
    output_ok = len(output_tree) == 1 and output_tree[0][0] == "F" and output_tree[0][1] == REPORT_NAME
    add("deliverable_scope", output_ok, f"entries={[item[1] for item in output_tree]}")
    if not output_ok:
        return checks, violations
    try:
        raw = report.read_bytes()
    except OSError as exc:
        add("document_parse", False, f"candidate_document_error:{type(exc).__name__}:{exc}")
        return checks, violations
    if len(raw) > 128 * 1024:
        add("document_parse", False, "document_too_large")
        return checks, violations
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        add("document_parse", False, "not_utf8")
        return checks, violations
    add("document_parse", text.startswith(f"{REPORT_TITLE}\n"), "utf8_markdown_title")
    first_section = "## 1. 结论摘要\n"
    preamble = text.split(first_section, 1)[0] if first_section in text else text
    add("document_preamble", preamble == f"{REPORT_TITLE}\n\n", "title_then_first_section_only")

    lowered = text.casefold()
    banned_patterns = {
        "superseded_source": r"\[S08\]",
        "superseded_rate": r"(?<!\d)30(?:\.0)?\s*%",
        "precision_overclaim": r"全市真实需求|必然发生|(?:就是|属于|等同于|(?<!不能)(?<!不得)视为)精确需求",
        "causal_overclaim": r"证明[^\n。|]{0,30}因果|系统导致[^\n。|]{0,30}(改善|提升)",
        "guarantee_overclaim": r"保证(收益|节约|回报|服务量)|guaranteed?\s+(saving|return)",
        "approval_overclaim": r"预算(已经|已)获批",
        "forbidden_action": r"(建议|应当|应该)[^\n。|]{0,20}(收购|购买)[^\n。|]{0,10}(地产|土地)",
        "roi_overclaim": r"(?<!不能作为)(?<!不得作为)已验证\s*(的)?\s*投资回报|verified\s+return on investment",
    }
    matches = [name for name, pattern in banned_patterns.items() if re.search(pattern, lowered, flags=re.I)]
    add("unsupported_or_forbidden_claims", not matches, f"matches={matches}")
    credential_patterns = (
        r"(?i)(?:api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*\S{8,}",
        r"(?i)\b(?:sk|hf)_[a-z0-9_-]{16,}\b",
        r"(?i)\bgithub_pat_[a-z0-9_]{16,}\b",
        r"(?i)\bwandb_v1_[a-z0-9_-]{16,}\b",
    )
    credential_matches = [pattern for pattern in credential_patterns if re.search(pattern, text)]
    add("no_secret_exposure", not credential_matches, f"pattern_count={len(credential_matches)}")
    unknown_citations = citations(text) - VALID_SOURCES
    add("citation_domain", not unknown_citations, f"unknown={sorted(unknown_citations)}")

    try:
        summary = section(text, "1. 结论摘要", "2. 关键指标")
        summary_lines = [line.strip() for line in summary.splitlines() if line.strip()]
        bullets = [line for line in summary_lines if line.startswith("-")]
        summary_families = (
            (("336000", "370440", "5.0"), {"S01"}),
            (("社区", "居家", "机构", "缺口", "规划"), {"S01", "S02", "S03"}),
            (("社区", "培训", "批准"), {"S04"}),
            (("1.5", "试点", "回收"), {"S06", "S07"}),
        )
        matched_families = {
            index
            for line in bullets
            for index, (terms, sources) in enumerate(summary_families)
            if all(term in line for term in terms) and citations(line) == sources
        }
        summary_lengths_ok = all(45 <= len(line) <= 240 for line in bullets)
        summary_ok = (
            len(summary_lines) == 4
            and len(bullets) == 4
            and matched_families == set(range(4))
            and summary_lengths_ok
        )
        add(
            "summary_evidence",
            summary_ok,
            f"bullet_count={len(bullets)},families={sorted(matched_families)},lengths_ok={summary_lengths_ok}",
        )

        metric_body = section(text, "2. 关键指标", "3. 证据链")
        claim_body = section(text, "3. 证据链", "4. 建议与优先级")
        recommendation_body = section(text, "4. 建议与优先级", "5. 风险与限制")
        risks = section(text, "5. 风险与限制", "6. 引用目录")
        bibliography_body = section(text, "6. 引用目录", None)
        risk_lines = [line.strip() for line in risks.splitlines() if line.strip()]
        structured_scope_ok = all(
            all(line.strip().startswith("|") for line in body.splitlines() if line.strip())
            for body in (metric_body, claim_body, recommendation_body, bibliography_body)
        ) and all(line.startswith("-") for line in risk_lines)
        add("structured_content_scope", structured_scope_ok, "tables_only_and_bullets_only")

        metric_rows = parse_table(metric_body, 5)
        by_metric = {row[0]: row for row in metric_rows}
        metric_ok = set(by_metric) == set(EXPECTED_METRICS) and len(by_metric) == len(metric_rows)
        metric_errors: list[str] = []
        if metric_ok:
            for metric_id, (value, unit, sources, terms) in EXPECTED_METRICS.items():
                row = by_metric[metric_id]
                if compact_number(row[1]) != value:
                    metric_errors.append(f"{metric_id}:value")
                if row[2] != unit:
                    metric_errors.append(f"{metric_id}:unit")
                if citations(row[4]) != sources:
                    metric_errors.append(f"{metric_id}:evidence")
                if not all(term in row[3] for term in terms):
                    metric_errors.append(f"{metric_id}:calculation")
        else:
            metric_errors.append("metric_id_set")
        add("numeric_consistency", not metric_errors, f"errors={metric_errors}")

        claim_rows = parse_table(claim_body, 4)
        by_claim = {row[0]: row for row in claim_rows}
        claim_errors: list[str] = []
        if set(by_claim) != set(EXPECTED_CLAIMS) or len(by_claim) != len(claim_rows):
            claim_errors.append("claim_id_set")
        else:
            for claim_id, (sources, conclusion_terms, limit_terms) in EXPECTED_CLAIMS.items():
                row = by_claim[claim_id]
                if citations(row[2]) != sources:
                    claim_errors.append(f"{claim_id}:evidence")
                if not all(term in row[1] for term in conclusion_terms):
                    claim_errors.append(f"{claim_id}:conclusion")
                if not all(term in row[3] for term in limit_terms):
                    claim_errors.append(f"{claim_id}:limit")
                if len(row[1]) < 14 or len(row[3]) < 12:
                    claim_errors.append(f"{claim_id}:insufficient_explanation")
        add("evidence_chain", not claim_errors, f"errors={claim_errors}")

        recommendation_rows = parse_table(recommendation_body, 5)
        by_recommendation = {row[0]: row for row in recommendation_rows}
        recommendation_errors: list[str] = []
        if set(by_recommendation) != set(EXPECTED_RECOMMENDATIONS) or len(by_recommendation) != len(recommendation_rows):
            recommendation_errors.append("recommendation_id_set")
        else:
            for rec_id, (priority, sources, action_terms, boundary_terms) in EXPECTED_RECOMMENDATIONS.items():
                row = by_recommendation[rec_id]
                if row[1] != priority:
                    recommendation_errors.append(f"{rec_id}:priority")
                if citations(row[3]) != sources:
                    recommendation_errors.append(f"{rec_id}:evidence")
                if not all(term in row[2] for term in action_terms):
                    recommendation_errors.append(f"{rec_id}:action")
                if not all(term in row[4] for term in boundary_terms):
                    recommendation_errors.append(f"{rec_id}:boundary")
                if len(row[2]) < 10 or len(row[4]) < 20:
                    recommendation_errors.append(f"{rec_id}:insufficient_explanation")
        add("actionable_recommendations", not recommendation_errors, f"errors={recommendation_errors}")

        risk_requirements = (("偏好", {"S02"}), ("规划", {"S01"}), ("因果", {"S06"}), ("成本", {"S07"}))
        risk_ok = (
            len(risk_lines) == 4
            and all(len(line) >= 30 for line in risk_lines)
            and all(
                any(term in line and citations(line) == sources for line in risk_lines)
                for term, sources in risk_requirements
            )
        )
        add("limitations_coverage", risk_ok, f"risk_count={len(risk_lines)}")

        bibliography_rows = parse_table(bibliography_body, 3)
        by_source = {row[0]: row for row in bibliography_rows}
        bibliography_errors: list[str] = []
        if set(by_source) != set(EXPECTED_BIBLIOGRAPHY) or len(by_source) != len(bibliography_rows):
            bibliography_errors.append("source_id_set")
        else:
            for source_id, expected in EXPECTED_BIBLIOGRAPHY.items():
                if tuple(by_source[source_id][1:]) != expected:
                    bibliography_errors.append(f"{source_id}:metadata")
        add("bibliography_traceability", not bibliography_errors, f"errors={bibliography_errors}")
    except Exception as exc:
        add("structured_report", False, f"{type(exc).__name__}:{exc}")

    return checks, violations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    try:
        checks, violations = verify_workspace(args.workspace.resolve(strict=True), args.case_root.resolve(strict=True))
        verdict = "accept" if not violations else "reject"
        score = sum(bool(check["passed"]) for check in checks) / len(checks) if checks else 0.0
        payload = {
            "schema_version": "case13_verifier_result_v1",
            "verdict": verdict,
            "score": round(score, 6),
            "checks": checks,
            "violations": violations,
        }
        exit_code = 0 if verdict == "accept" else 1
    except Exception as exc:
        payload = {
            "schema_version": "case13_verifier_result_v1",
            "verdict": "invalid",
            "score": 0.0,
            "checks": [],
            "violations": [f"verifier_error:{type(exc).__name__}:{exc}"],
        }
        exit_code = 2
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.result:
        args.result.write_text(encoded, encoding="utf-8")
    sys.stdout.write(encoded)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
