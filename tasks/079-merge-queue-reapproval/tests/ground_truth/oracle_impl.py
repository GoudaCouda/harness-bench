from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

HEADER = ["gate", "sha", "status", "next_action", "evidence"]
GATES = (
    "build_linux",
    "build_windows",
    "security",
    "license",
    "owner_approval",
    "release_approval",
)
EXPECTED = {
    "build_linux": ("pass", "none", "current_checks.json"),
    "build_windows": ("pass", "none", "current_checks.json"),
    "security": ("pending", "wait", "current_checks.json"),
    "license": ("fail", "remediate", "current_checks.json"),
    "owner_approval": ("stale", "reapproval", "current_reviews.json"),
    "release_approval": ("pass", "none", "current_reviews.json"),
}


def _norm(value: Any) -> str:
    return re.sub(r"[\s_:/-]+", " ", str(value or "").strip().casefold())


def _canonical_gate(value: Any) -> str | None:
    aliases = {
        "build linux": "build_linux",
        "linux build": "build_linux",
        "build windows": "build_windows",
        "windows build": "build_windows",
        "security": "security",
        "security scan": "security",
        "license": "license",
        "license scan": "license",
        "owner approval": "owner_approval",
        "codeowner approval": "owner_approval",
        "release approval": "release_approval",
    }
    return aliases.get(_norm(value))


def _status_ok(gate: str, value: Any) -> bool:
    normalized = _norm(value)
    expected = EXPECTED[gate][0]
    aliases = {
        "pass": {"pass", "passed", "success", "approved", "satisfied"},
        "pending": {"pending", "running", "in progress", "awaiting"},
        "fail": {"fail", "failed", "failure", "blocked"},
        "stale": {"stale", "pending", "missing", "invalidated", "needs reapproval"},
    }
    return normalized in aliases[expected]


def _action_ok(gate: str, value: Any) -> bool:
    normalized = _norm(value)
    kind = EXPECTED[gate][1]
    if kind == "none":
        return normalized in {"", "none", "no action", "noop", "satisfied"}
    if kind == "wait":
        return any(
            term in normalized for term in ("wait", "await", "scan", "completion")
        )
    if kind == "remediate":
        return any(
            term in normalized
            for term in (
                "remediat",
                "replace dependency",
                "fix dependency",
                "resolve license",
            )
        ) and any(term in normalized for term in ("rerun", "re run", "run again"))
    return any(
        term in normalized
        for term in (
            "reapproval",
            "re approve",
            "reapprove",
            "request current sha approval",
            "request approval",
        )
    ) or bool(re.search(r"\b(?:re\s+)?request\b.{0,40}\bapproval\b", normalized))


def _evidence_ok(value: Any, expected_file: str) -> bool:
    references = {
        Path(part.split(":", 1)[0].strip()).name
        for part in str(value or "").split(";")
        if part.strip()
    }
    return expected_file in references


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
        with (root / "queue_gates.csv").open(
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
    canonical = [(_canonical_gate(row.get("gate")), row) for row in rows]
    by_gate = {gate: row for gate, row in canonical if gate is not None}
    integrity = (
        header == HEADER
        and len(rows) == len(by_gate) == len(GATES)
        and set(by_gate) == set(GATES)
    )
    _add(
        checks,
        "ledger_integrity",
        integrity,
        {"header": header, "gates": sorted(by_gate)},
    )

    row_results: dict[str, bool] = {}
    for gate in GATES:
        row = by_gate.get(gate, {})
        detail = {
            "sha": row.get("sha") == "bbb222",
            "status": _status_ok(gate, row.get("status")),
            "next_action": _action_ok(gate, row.get("next_action")),
            "evidence": _evidence_ok(row.get("evidence"), EXPECTED[gate][2]),
        }
        row_results[gate] = all(detail.values())
        _add(checks, f"gate_row_{gate}", row_results[gate], detail)
    _add(
        checks,
        "gate_build",
        row_results.get("build_linux", False)
        and row_results.get("build_windows", False),
    )
    _add(checks, "gate_security", row_results.get("security", False))
    _add(checks, "gate_license", row_results.get("license", False))
    _add(checks, "gate_owner_approval", row_results.get("owner_approval", False))
    _add(checks, "gate_release_approval", row_results.get("release_approval", False))

    state: dict[str, Any] = {}
    try:
        candidate = json.loads((root / "queue_state.json").read_text(encoding="utf-8"))
        if isinstance(candidate, dict):
            state = candidate
    except Exception:
        state = {}
    pending = state.get("pending_gates")
    canonical_pending = (
        [_canonical_gate(value) for value in pending]
        if isinstance(pending, list)
        else []
    )
    state_detail = {
        "current_sha": state.get("current_sha") == "bbb222",
        "previous_sha": state.get("previous_sha") == "aaa111",
        "queue_state": _norm(state.get("queue_state"))
        in {"blocked revalidation", "pending revalidation", "blocked", "pending"},
        "merge_not_executed": state.get("merge_executed") is False,
        "pending_gates": isinstance(pending, list)
        and None not in canonical_pending
        and len(canonical_pending) == 3
        and set(canonical_pending) == {"security", "license", "owner_approval"},
    }
    _add(checks, "aggregate_state", all(state_detail.values()), state_detail)

    path = root / "transition.md"
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    normalized = _norm(text)
    invalidation = (
        all(sha in normalized for sha in ("aaa111", "bbb222"))
        and any(
            term in normalized
            for term in ("conflict resolution", "new commit", "late commit")
        )
        and "owner" in normalized
        and any(term in normalized for term in ("stale", "cannot carry", "invalidat"))
        and "release" in normalized
        and any(term in normalized for term in ("satisfied", "approved", "pass"))
    )
    handoff = (
        all(term in normalized for term in ("security", "license", "owner approval"))
        and "gpl" in normalized
        and any(term in normalized for term in ("remediat", "replace dependency"))
        and any(
            term in normalized
            for term in (
                "not been merged",
                "no merge",
                "has not been merged",
                "cannot merge",
            )
        )
        and any(term in normalized for term in ("verify", "verification", "reconcile"))
    )
    _add(checks, "transition_invalidation", invalidation)
    _add(checks, "transition_handoff", handoff)
    return {
        "task": "079-merge-queue-reapproval",
        "workspace": str(root),
        "outcome_score": sum(bool(check["pass"]) for check in checks) / len(checks),
        "checks": checks,
    }
