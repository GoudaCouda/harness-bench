from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

TASK_DIR = Path(__file__).resolve().parents[2]
GT_PATH = TASK_DIR / "tests" / "ground_truth" / "ground_truth.json"
HEADER = ["item", "type", "impact", "recommended_fix"]


def _norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).casefold()


def _has_group(text: object, group: list[str]) -> bool:
    haystack = _norm(text)
    return any(_norm(term) in haystack for term in group)


def _all_groups(text: object, groups: list[list[str]]) -> bool:
    return all(_has_group(text, group) for group in groups)


def _claim_sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"^###\s+Claim\s+(CLAIM-\d+)\s*$", text, re.I | re.M))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1).upper()] = text[match.end() : end]
    return sections


def score_workspace(
    workspace: Path, *, ground_truth_path: Path | None = None
) -> dict[str, Any]:
    w = workspace.resolve()
    gt = json.loads((ground_truth_path or GT_PATH).read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []

    def add(cid: str, ok: bool, detail: Any = None) -> None:
        checks.append(
            {
                "id": cid,
                "label": cid.replace("_", " "),
                "pass": bool(ok),
                "weight": 1.0,
                "detail": detail,
            }
        )

    report_path = w / "reproducibility_report.md"
    report = ""
    readable = False
    if report_path.is_file():
        try:
            report = report_path.read_text(encoding="utf-8")
            readable = bool(report.strip()) and "\x00" not in report
        except (OSError, UnicodeError):
            pass
    sections = _claim_sections(report) if readable else {}
    add("claim_sections", set(sections) == set(gt["claim_ids"]), sorted(sections))
    claim_ok: dict[str, bool] = {}
    for claim_id in gt["claim_ids"]:
        section = sections.get(claim_id, "")
        claim_ok[claim_id] = len(section.strip()) >= 160 and _all_groups(
            section, gt["claim_groups"][claim_id]
        )
        add(
            f"claim_{claim_id.removeprefix('CLAIM-')}_evidence",
            claim_ok[claim_id],
            {"claim_id": claim_id},
        )
    add("claim_evidence_binding", all(claim_ok.values()), claim_ok)
    add("required_terms", readable and _all_groups(report, gt["execution_groups"]))

    lowered = _norm(report)
    false_success = [
        phrase for phrase in gt["forbidden_success_phrases"] if _norm(phrase) in lowered
    ]
    add("no_false_repro", readable and not false_success, false_success)

    conclusion_matches = list(
        re.finditer(
            r"(?im)^(?:#{1,6}\s+|\*\*)?(?:package\s+)?conclusion(?:\*\*)?\s*:?[ \t]*$",
            report,
        )
    )
    conclusion = report[conclusion_matches[-1].start() :] if conclusion_matches else ""
    conclusion_ok = (
        bool(conclusion)
        and _has_group(conclusion, ["ran", "runnable", "execution"])
        and (
            _has_group(
                conclusion,
                ["not reproduced", "cannot be reproduced", "does not reproduce"],
            )
            or bool(re.search(r"\bno\b[^.!?]{0,48}\breproduced\b", conclusion, re.I))
        )
        and _has_group(
            conclusion,
            ["snapshot", "freeze", "version", "sample dataset", "full dataset", "deposit"],
        )
        and _has_group(conclusion, ["subgroup"])
    )
    add("package_conclusion", conclusion_ok)

    ledger_path = w / "missing_steps.csv"
    rows: list[dict[str, str]] = []
    header: list[str] = []
    if ledger_path.is_file():
        try:
            with ledger_path.open(newline="", encoding="utf-8-sig") as stream:
                reader = csv.DictReader(stream)
                header = list(reader.fieldnames or [])
                rows = list(reader)
            add("missing_csv_parseable", True)
        except (OSError, UnicodeError, csv.Error) as exc:
            add("missing_csv_parseable", False, str(exc))
    else:
        add("missing_csv_parseable", False, "missing")
    add("missing_csv_header_line", header == HEADER, header)

    matched_indices: set[int] = set()
    blocker_results: list[bool] = []
    for blocker in gt["blockers"]:
        matches: list[int] = []
        for index, row in enumerate(rows):
            if (
                _all_groups(row.get("item"), blocker["item_groups"])
                and _all_groups(row.get("type"), blocker["type_groups"])
                and _all_groups(row.get("impact"), blocker["impact_groups"])
                and bool(str(row.get("recommended_fix") or "").strip())
            ):
                matches.append(index)
        blocker_results.append(len(matches) == 1)
        matched_indices.update(matches)
    closed = (
        len(rows) == len(gt["blockers"])
        and len(matched_indices) == len(rows)
        and all(blocker_results)
    )
    add(
        "missing_expectation_coverage",
        closed,
        {
            "matched": len(matched_indices),
            "rows": len(rows),
            "blockers": blocker_results,
        },
    )
    add(
        "missing_csv_columns",
        bool(rows)
        and header == HEADER
        and all(
            set(row) == set(HEADER)
            and None not in row
            and all(str(row.get(column) or "").strip() for column in HEADER)
            for row in rows
        ),
    )

    score = (
        sum(bool(check["pass"]) for check in checks) / len(checks) if checks else 0.0
    )
    return {
        "task": "048-research-repro-package",
        "workspace": str(w),
        "outcome_score": round(score, 4),
        "checks": checks,
    }
