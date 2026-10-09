from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

HEADER = [
    "job",
    "classification",
    "action",
    "final_attempt",
    "final_status",
    "evidence",
]
# Keep historical jobs first so existing diagnostic check IDs remain stable.
EXPECTED = {
    "unit": ("valid", "preserve", 1, "pass", "attempt1.json"),
    "windows": ("runner", "rerun", 2, "pass", "retry_update.json"),
    "integration": ("code", "patch_run", 2, "pass", "patch_evidence.json"),
    "package": ("stale", "current_sha", 2, "pass", "package_update.json"),
    "lint": ("valid", "preserve", 1, "pass", "attempt1.json"),
    "macos": ("runner_exhausted", "escalate", 2, "runner_lost", "retry_update.json"),
    "docs": ("code", "patch_required", 1, "broken_link", "attempt1.json"),
    "e2e": ("upstream_cancelled", "wait", 1, "cancelled", "attempt1.json"),
}


def _norm(value: Any) -> str:
    return re.sub(r"[\s_:/-]+", " ", str(value or "").strip().casefold())


def _classification(value: Any, expected: str) -> bool:
    normalized = _norm(value)
    aliases = {
        "valid": ("valid success", "success", "passed", "current head pass"),
        "runner": ("runner", "infrastructure", "infra failure", "recoverable failure"),
        "runner_exhausted": (
            "runner retry exhausted",
            "runner exhausted",
            "repeated runner",
            "infrastructure retry exhausted",
        ),
        "code": ("code failure", "assertion", "deterministic failure", "broken link"),
        "stale": ("stale artifact", "stale sha", "old sha artifact"),
        "upstream_cancelled": (
            "upstream cancelled",
            "fail fast",
            "dependency cancelled",
            "blocked cancellation",
        ),
    }
    return any(term in normalized for term in aliases[expected])


def _action(value: Any, expected: str) -> bool:
    normalized = _norm(value)
    aliases = {
        "preserve": ("preserve", "keep", "no rerun", "reuse"),
        "rerun": ("retry", "rerun"),
        "patch_run": ("patch then run", "fix then run", "patch and rerun"),
        "current_sha": ("update", "replace", "rebuild", "current sha"),
        "escalate": ("escalate", "operator", "no third retry"),
        "patch_required": (
            "patch required",
            "fix required",
            "await patch",
            "block for patch",
        ),
        "wait": ("wait", "hold", "after blockers", "pending blockers"),
    }
    return any(term in normalized for term in aliases[expected])


def _attempt(value: Any, expected: int) -> bool:
    if isinstance(value, bool):
        return False
    try:
        return int(str(value).strip()) == expected
    except (TypeError, ValueError):
        return False


def _status(value: Any, expected: str) -> bool:
    normalized = _norm(value)
    aliases = {
        "pass": {"pass", "passed", "success", "successful"},
        "runner_lost": {"runner lost", "runner failure", "infrastructure failure"},
        "broken_link": {"broken link", "failed", "code failure", "blocked"},
        "cancelled": {
            "cancelled fail fast",
            "cancelled",
            "canceled",
            "waiting",
            "pending",
        },
    }
    return normalized in aliases[expected]


def _evidence(value: Any, expected_file: str) -> bool:
    references = {
        Path(part.split(":", 1)[0].strip()).name
        for part in str(value or "").split(";")
        if part.strip()
    }
    return expected_file in references


def _string_set(value: Any) -> set[str] | None:
    return {_norm(item) for item in value} if isinstance(value, list) else None


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
        with (root / "job_ledger.csv").open(
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
    by_job = {row["job"].casefold(): row for row in rows}
    integrity = (
        header == HEADER
        and len(rows) == len(by_job) == len(EXPECTED)
        and set(by_job) == set(EXPECTED)
    )
    _add(
        checks,
        "ledger_integrity",
        integrity,
        {"header": header, "jobs": sorted(by_job)},
    )
    for index, (job, expected) in enumerate(EXPECTED.items(), start=1):
        row = by_job.get(job, {})
        detail = {
            "classification": _classification(row.get("classification"), expected[0]),
            "action": _action(row.get("action"), expected[1]),
            "attempt": _attempt(row.get("final_attempt"), expected[2]),
            "final_status": _status(row.get("final_status"), expected[3]),
            "evidence": _evidence(row.get("evidence"), expected[4]),
        }
        _add(checks, f"ledger_item_{index}", all(detail.values()), detail)

    state: dict[str, Any] = {}
    try:
        candidate = json.loads((root / "run_state.json").read_text(encoding="utf-8"))
        if isinstance(candidate, dict):
            state = candidate
    except Exception:
        state = {}
    budget = state.get("retry_budget_used")
    budget_ok = isinstance(budget, dict) and {
        _norm(key): value for key, value in budget.items()
    } == {"windows": 1, "macos": 1}
    state_detail = {
        "head_sha": str(state.get("head_sha") or "").strip() == "91ac2e",
        "retry_budget": budget_ok,
        "preserved_jobs": _string_set(state.get("preserved_jobs")) == {"unit", "lint"},
        "pending_jobs": _string_set(state.get("pending_jobs"))
        == {"macos", "docs", "e2e"},
        "artifact_digest": str(state.get("artifact_digest") or "").strip()
        == "sha256:new91",
        "status": any(
            term in _norm(state.get("status"))
            for term in ("blocked", "pending recovery", "needs action")
        ),
    }
    _add(checks, "aggregate_state", all(state_detail.values()), state_detail)

    report_path = root / "diagnosis.md"
    report = (
        report_path.read_text(encoding="utf-8", errors="replace")
        if report_path.is_file()
        else ""
    )
    normalized = _norm(report)
    report_detail = {
        "runner": all(job in normalized for job in ("windows", "macos"))
        and "retry" in normalized
        and any(term in normalized for term in ("exhausted", "no third", "escalat")),
        "code": all(job in normalized for job in ("integration", "docs"))
        and "patch" in normalized
        and any(
            term in normalized
            for term in ("no patch", "without patch", "remains blocked")
        ),
        "preserved": all(job in normalized for job in ("unit", "lint"))
        and "preserv" in normalized,
        "dependency": "e2e" in normalized
        and "fail fast" in normalized
        and any(term in normalized for term in ("wait", "block")),
        "artifact": "package" in normalized
        and "sha256 new91" in normalized
        and any(term in normalized for term in ("current head", "91ac2e")),
        "verification": "eight" in normalized
        and any(term in normalized for term in ("verify", "verification", "reconcile")),
        "external_boundary": "offline" in normalized
        and bool(re.search(r"\bno\b.{0,100}\bexternal action\b", normalized)),
    }
    _add(checks, "evidence_report", all(report_detail.values()), report_detail)

    pending_from_rows = {
        job
        for job, row in by_job.items()
        if not _status(row.get("final_status"), "pass")
    }
    closure = (
        integrity
        and pending_from_rows == {"macos", "docs", "e2e"}
        and _string_set(state.get("pending_jobs")) == pending_from_rows
        and _string_set(state.get("preserved_jobs")) == {"unit", "lint"}
        and str(state.get("artifact_digest") or "").strip() == "sha256:new91"
        and state_detail["status"]
    )
    _add(
        checks, "recovery_closure", closure, {"pending_jobs": sorted(pending_from_rows)}
    )
    return {
        "task": "070-ci-attempt-diagnosis",
        "workspace": str(root),
        "outcome_score": sum(bool(check["pass"]) for check in checks) / len(checks),
        "checks": checks,
    }
