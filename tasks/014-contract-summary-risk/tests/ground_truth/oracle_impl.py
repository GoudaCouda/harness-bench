from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

_TASK_DIR = Path(__file__).resolve().parents[2]
_GT = _TASK_DIR / "tests" / "ground_truth" / "ground_truth.json"
_HEADER = [
    "source",
    "clause_id",
    "risk",
    "severity",
    "recommended_action",
    "owner",
]


def _norm(value: object) -> str:
    text = re.sub(r"[-‐‑‒–—]+", " ", str(value or "").strip())
    return re.sub(r"\s+", " ", text).casefold()


def _has_any(text: object, terms: list[str]) -> bool:
    haystack = _norm(text)
    return any(_norm(term) in haystack for term in terms)


def _all_groups(text: object, groups: list[list[str]]) -> bool:
    return all(_has_any(text, group) for group in groups)


def _contains_unnegated(text: str, term: str) -> bool:
    lowered = text.casefold()
    needle = term.casefold()
    start = 0
    while (index := lowered.find(needle, start)) >= 0:
        prefix = lowered[max(0, index - 52) : index]
        if not re.search(
            r"(?:\bnot\b|\bno\b|\bnever\b|\bwithout\b|"
            r"\bdoes(?:n't| not)\b|\bis(?:n't| not)\b)[^.!?]{0,36}$",
            prefix,
        ):
            return True
        start = index + len(needle)
    return False


def score_workspace(
    workspace: Path, *, ground_truth_path: Path | None = None
) -> dict[str, Any]:
    w = workspace.resolve()
    gt = json.loads((ground_truth_path or _GT).read_text(encoding="utf-8"))
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

    rows: list[dict[str, str]] = []
    header: list[str] = []
    ledger = w / "risk_clauses.csv"
    if ledger.is_file():
        try:
            with ledger.open(newline="", encoding="utf-8") as stream:
                reader = csv.DictReader(stream)
                header = list(reader.fieldnames or [])
                rows = list(reader)
            add("risk_csv_parseable", True)
        except (OSError, UnicodeError, csv.Error) as exc:
            add("risk_csv_parseable", False, str(exc))
    else:
        add("risk_csv_parseable", False, "missing")

    add("risk_csv_header_exact", header == _HEADER, header)
    expected = gt["expected_risks"]
    expected_keys = {(item["source"], item["clause_id"]) for item in expected}
    actual_keys = {
        (
            Path(str(row.get("source") or "")).name,
            str(row.get("clause_id") or "").strip(),
        )
        for row in rows
    }
    add(
        "closed_risk_set",
        len(rows) == len(expected)
        and len(actual_keys) == len(rows)
        and actual_keys == expected_keys,
        {"expected": sorted(expected_keys), "actual": sorted(actual_keys)},
    )

    row_results: list[bool] = []
    for item in expected:
        matches = [
            row
            for row in rows
            if Path(str(row.get("source") or "")).name == item["source"]
            and str(row.get("clause_id") or "").strip() == item["clause_id"]
        ]
        ok = len(matches) == 1
        if ok:
            row = matches[0]
            ok = (
                _has_any(row.get("risk"), item["risk_terms"])
                and _all_groups(row.get("recommended_action"), item["action_groups"])
                and _all_groups(row.get("owner"), item["owner_groups"])
            )
        row_results.append(ok)
        add(f"risk_{item['clause_id']}", ok, item)

    add(
        "risk_actions_and_owners",
        bool(row_results) and all(row_results),
        {"complete": sum(row_results), "expected": len(row_results)},
    )
    add(
        "severity_values_valid",
        bool(rows)
        and all(
            str(row.get("severity") or "") in {"High", "Medium", "Low"} for row in rows
        ),
    )
    add(
        "unique_clause_keys",
        bool(rows) and len(actual_keys) == len(rows),
    )

    summary_path = w / "contract_summary.md"
    summary = ""
    readable = False
    if summary_path.is_file():
        try:
            summary = summary_path.read_text(encoding="utf-8")
            readable = bool(summary.strip()) and "\x00" not in summary
        except (OSError, UnicodeError):
            pass
    missing_effective = [
        group
        for group in gt["effective_summary_groups"]
        if not _has_any(summary, group)
    ]
    missing_risks = [
        group for group in gt["summary_risk_groups"] if not _has_any(summary, group)
    ]
    add(
        "summary_effective_terms",
        readable and not missing_effective,
        {"missing_groups": missing_effective},
    )
    add(
        "summary_open_risks",
        readable and not missing_risks,
        {"missing_groups": missing_risks},
    )
    forbidden = [
        term for term in gt["forbidden_terms"] if _contains_unnegated(summary, term)
    ]
    add(
        "summary_review_boundary",
        readable and not forbidden,
        {"forbidden": forbidden, "readable": readable},
    )

    score = (
        sum(bool(check["pass"]) for check in checks) / len(checks) if checks else 0.0
    )
    return {
        "task": "014-contract-summary-risk",
        "workspace": str(w),
        "outcome_score": round(score, 4),
        "checks": checks,
    }
