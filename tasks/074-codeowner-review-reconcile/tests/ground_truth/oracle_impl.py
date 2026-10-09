from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

HEADER = ["path", "owner", "approval", "reviewer", "reason"]
EXPECTED = {
    "src/payments/core.py": ("payments", "satisfied", {"paya"}, "current"),
    "src/payments/generated/client.py": ("platform", "missing", {"", "platb"}, "stale"),
    "infra/payment-job.json": ("sre", "blocked", {"srec"}, "blocked"),
    "docs/payments/runbook.md": ("payments docs", "satisfied", {"doca"}, "current"),
    "config/secrets/payment.yaml": ("security", "satisfied", {"seca"}, "current"),
    "scripts/release-payments.sh": ("release", "missing", {"", "rela"}, "dismissed"),
    "src/shared/logging.py": ("platform", "satisfied", {"platd"}, "scoped"),
    ".github/workflows/payment.yml": ("ci", "satisfied", {"cia"}, "current"),
}
SATISFIED = {path for path, expected in EXPECTED.items() if expected[1] == "satisfied"}
MISSING = {path for path, expected in EXPECTED.items() if expected[1] == "missing"}
BLOCKED = {path for path, expected in EXPECTED.items() if expected[1] == "blocked"}


def _norm(value: Any) -> str:
    return re.sub(r"[\s_:/-]+", " ", str(value or "").strip().casefold())


def _reviewer(value: Any) -> str:
    normalized = _norm(value)
    return "" if normalized in {"", "none", "n a", "na", "not assigned"} else normalized


def _approval(row: dict[str, str]) -> str | None:
    value = _norm(row.get("approval"))
    reason = _norm(row.get("reason"))
    if value in {"satisfied", "approved", "current approval", "true", "yes"}:
        return "satisfied"
    if value in {
        "missing",
        "needs approval",
        "approval required",
        "stale",
        "dismissed",
    }:
        return "missing"
    if value in {"blocked", "changes requested", "rejected"}:
        return "blocked"
    if value in {"false", "no"}:
        if any(
            term in reason
            for term in (
                "stale",
                "old sha",
                "missing",
                "dismiss",
                "approval required",
                "no valid approval",
                "no qualifying approval",
            )
        ):
            return "missing"
        if any(
            term in reason
            for term in ("changes requested", "change requested", "blocked")
        ):
            return "blocked"
    return None


def _reason_ok(value: Any, kind: str) -> bool:
    normalized = _norm(value)
    aliases = {
        "current": ("current", "approv", "reviews json"),
        "stale": ("stale", "old sha", "old100", "path scoped"),
        "blocked": ("changes requested", "change requested", "blocked"),
        "dismissed": ("dismiss", "no qualifying", "missing"),
        "scoped": ("scoped", "path approval", "current approv", "approved by owner"),
    }
    return any(term in normalized for term in aliases[kind])


def _bucket_ok(value: Any, expected_paths: set[str]) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value == len(expected_paths)
    if isinstance(value, list):
        paths = [str(item).strip() for item in value]
        return len(paths) == len(expected_paths) and set(paths) == expected_paths
    return False


def _add(
    checks: list[dict[str, Any]], check_id: str, passed: bool, detail: Any = None
) -> None:
    checks.append(
        {
            "id": check_id,
            "label": check_id.replace("_", " "),
            "pass": bool(passed),
            "weight": 1.0,
            "detail": detail,
        }
    )


def score_workspace(
    workspace: Path, *, ground_truth_path: Path | None = None
) -> dict[str, Any]:
    del ground_truth_path
    root = Path(workspace).resolve()
    checks: list[dict[str, Any]] = []
    rows: list[dict[str, str]] = []
    header: list[str] = []
    try:
        with (root / "path_coverage.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            reader = csv.DictReader(handle)
            header = list(reader.fieldnames or [])
            rows = [
                {field: str(row.get(field) or "").strip() for field in HEADER}
                for row in reader
                if None not in row
            ]
    except Exception:
        rows = []
    by_path = {row["path"]: row for row in rows}
    integrity = (
        header == HEADER
        and len(rows) == len(by_path) == len(EXPECTED)
        and set(by_path) == set(EXPECTED)
    )
    _add(
        checks,
        "ledger_integrity",
        integrity,
        {"header": header, "paths": sorted(by_path)},
    )
    for index, (path, expected) in enumerate(EXPECTED.items(), start=1):
        row = by_path.get(path, {})
        detail = {
            "owner": _norm(row.get("owner")) == expected[0],
            "approval": _approval(row) == expected[1],
            "reviewer": _reviewer(row.get("reviewer")) in expected[2],
            "reason": _reason_ok(row.get("reason"), expected[3]),
        }
        _add(checks, f"ledger_item_{index}", all(detail.values()), detail)

    state: dict[str, Any] = {}
    try:
        candidate = json.loads((root / "review_state.json").read_text(encoding="utf-8"))
        if isinstance(candidate, dict):
            state = candidate
    except Exception:
        state = {}
    bucket_types = {
        type(state.get(name)) for name in ("satisfied", "missing", "blocked")
    }
    consistent = len(bucket_types) == 1 and bucket_types <= {int, list}
    _add(checks, "state_head_sha", state.get("head_sha") == "e4b201")
    _add(
        checks,
        "state_satisfied",
        consistent and _bucket_ok(state.get("satisfied"), SATISFIED),
    )
    _add(
        checks,
        "state_missing",
        consistent and _bucket_ok(state.get("missing"), MISSING),
    )
    _add(
        checks,
        "state_blocked",
        consistent and _bucket_ok(state.get("blocked"), BLOCKED),
    )
    _add(
        checks,
        "state_decision",
        _norm(state.get("decision"))
        in {"blocked", "rejected", "not approved", "cannot merge"},
    )

    report_path = root / "review_request.md"
    report = (
        report_path.read_text(encoding="utf-8", errors="replace")
        if report_path.is_file()
        else ""
    )
    normalized = _norm(report)
    _add(
        checks,
        "report_precedence",
        "last matching" in normalized
        and "generated" in normalized
        and "platform" in normalized,
    )
    _add(
        checks,
        "report_stale_approval",
        "platb" in normalized
        and any(term in normalized for term in ("stale", "old sha", "old100"))
        and "platd" in normalized
        and "scoped" in normalized
        and "rela" in normalized
        and "dismiss" in normalized,
    )
    followup_ok = (
        (
            "platform" in normalized
            and "generated" in normalized
            and "approval" in normalized
        )
        and (
            "release" in normalized
            and "script" in normalized
            and "approval" in normalized
        )
    ) or any(
        term in normalized
        for term in ("platform approval", "release approval", "re review", "reapproval")
    )
    _add(
        checks,
        "report_block",
        "sre" in normalized
        and "srec" in normalized
        and "change" in normalized
        and "request" in normalized
        and "block" in normalized
        and followup_ok,
    )
    execution_claim = re.search(
        r"\b(?:we|i)\s+(?:have\s+)?(?:requested|merged|deployed|published)\b|"
        r"\b(?:review request|merge|deployment)\s+(?:was|has been)\s+(?:sent|executed|completed)\b",
        normalized,
    )
    _add(
        checks,
        "report_verification_safety",
        any(term in normalized for term in ("verify", "verification", "reconcile"))
        and execution_claim is None,
    )
    return {
        "task": "074-codeowner-review-reconcile",
        "workspace": str(root),
        "outcome_score": sum(bool(check["pass"]) for check in checks) / len(checks),
        "checks": checks,
    }
