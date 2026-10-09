from __future__ import annotations

import csv
import json
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

_TASK_DIR = Path(__file__).resolve().parents[2]
_GT = _TASK_DIR / "tests" / "ground_truth" / "ground_truth.json"
_HEADER = [
    "expense_id",
    "employee",
    "claimed_usd",
    "allowed_usd",
    "status",
    "reason",
    "recommended_action",
]


def _money(value: object) -> Decimal | None:
    try:
        text = str(value or "").strip()
        if "$" in text or not re.fullmatch(r"-?\d+(?:\.\d{1,2})?", text):
            return None
        return Decimal(text).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def _contains_all(text: object, terms: list[str]) -> bool:
    lowered = re.sub(r"\s+", " ", str(text or "")).casefold()
    aliases = {
        "approval": ("approval", "approved"),
        "authorization": ("authorization", "authorized"),
    }
    return all(
        any(
            candidate in lowered
            for candidate in aliases.get(term.casefold(), (term.casefold(),))
        )
        for term in terms
    )


def _text_money(text: str, expected: str) -> bool:
    wanted = Decimal(expected)
    for token in re.findall(
        r"(?<![A-Za-z0-9])\$?\s*([0-9][0-9,]*(?:\.\d{1,2})?)", text
    ):
        try:
            if Decimal(token.replace(",", "")).quantize(Decimal("0.01")) == wanted:
                return True
        except InvalidOperation:
            continue
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
    path = w / "reimbursement_audit.csv"
    if path.is_file():
        try:
            with path.open(newline="", encoding="utf-8") as stream:
                reader = csv.DictReader(stream)
                header = list(reader.fieldnames or [])
                rows = list(reader)
            add("audit_csv_parseable", True)
        except (OSError, UnicodeError, csv.Error) as exc:
            add("audit_csv_parseable", False, str(exc))
    else:
        add("audit_csv_parseable", False, "missing")
    add("audit_header_exact", header == _HEADER, header)

    expected: dict[str, dict[str, str]] = gt["expenses"]
    actual_ids = [str(row.get("expense_id") or "").strip() for row in rows]
    add(
        "closed_expense_set",
        len(rows) == len(expected)
        and len(actual_ids) == len(set(actual_ids))
        and set(actual_ids) == set(expected),
        {"expected": sorted(expected), "actual": sorted(actual_ids)},
    )

    line_results: list[bool] = []
    money_results: list[bool] = []
    by_id = {str(row.get("expense_id") or "").strip(): row for row in rows}
    for expense_id, item in expected.items():
        row = by_id.get(expense_id, {})
        money_ok = _money(row.get("claimed_usd")) == Decimal(
            item["claimed_usd"]
        ) and _money(row.get("allowed_usd")) == Decimal(item["allowed_usd"])
        disposition_ok = (
            bool(row)
            and str(row.get("employee") or "").strip() == item["employee"]
            and str(row.get("status") or "").strip().casefold() == item["status"]
            and _contains_all(row.get("reason"), item["reason_terms"])
            and bool(str(row.get("recommended_action") or "").strip())
        )
        money_results.append(money_ok)
        line_results.append(disposition_ok and money_ok)
        add(f"expense_{expense_id}", disposition_ok and money_ok, item)
    add("line_money_values", bool(money_results) and all(money_results))

    claimed = sum((_money(row.get("claimed_usd")) or Decimal("0")) for row in rows)
    allowed = sum((_money(row.get("allowed_usd")) or Decimal("0")) for row in rows)
    add(
        "batch_money_totals",
        len(rows) == len(expected)
        and claimed == Decimal(gt["total_claimed_usd"])
        and allowed == Decimal(gt["total_allowed_usd"]),
        {"claimed": str(claimed), "allowed": str(allowed)},
    )
    status_counts = Counter(
        str(row.get("status") or "").strip().casefold() for row in rows
    )
    add(
        "ledger_integrity",
        bool(rows)
        and header == _HEADER
        and len(actual_ids) == len(set(actual_ids))
        and all(
            status in {"approved", "adjusted", "pending", "rejected"}
            for status in status_counts
        )
        and all(
            _money(row.get("claimed_usd")) is not None
            and _money(row.get("allowed_usd")) is not None
            for row in rows
        ),
    )

    memo_path = w / "missing_docs.md"
    memo = ""
    readable = False
    if memo_path.is_file():
        try:
            memo = memo_path.read_text(encoding="utf-8")
            readable = bool(memo.strip()) and "\x00" not in memo
        except (OSError, UnicodeError):
            pass
    documentation_ok = readable
    for expense_id, terms in gt["documentation_items"].items():
        documentation_ok = (
            documentation_ok and expense_id in memo and _contains_all(memo, terms)
        )
    add("documentation_exception_handoff", documentation_ok)

    counts_ok = readable
    for status, count in gt["status_counts"].items():
        counts_ok = counts_ok and bool(
            re.search(
                rf"(?:\b{count}\b[^.!?\n]{{0,24}}\b{re.escape(status)}\b|\b{re.escape(status)}\b[^.!?\n]{{0,24}}\b{count}\b)",
                memo,
                re.I,
            )
        )
    add(
        "status_count_handoff",
        counts_ok
        and _text_money(memo, gt["total_claimed_usd"])
        and _text_money(memo, gt["total_allowed_usd"]),
    )
    payment_claim = bool(
        re.search(
            r"\b(?:paid|payment issued|reimbursed|posted to payroll)\b", memo, re.I
        )
    )
    payment_disclaimed = bool(
        re.search(
            r"\b(?:no|not)\b[^.!?]{0,24}\b(?:paid|payment|reimbursed|issued)\b",
            memo,
            re.I,
        )
    )
    add("payment_boundary", readable and (not payment_claim or payment_disclaimed))

    score = (
        sum(bool(check["pass"]) for check in checks) / len(checks) if checks else 0.0
    )
    return {
        "task": "016-expense-packet-review",
        "workspace": str(w),
        "outcome_score": round(score, 4),
        "checks": checks,
    }
