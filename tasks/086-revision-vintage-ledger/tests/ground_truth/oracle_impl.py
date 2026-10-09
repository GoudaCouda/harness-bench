from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path
from typing import Any

HEADER = ["series", "month", "preliminary", "revised", "delta", "adjustment"]
EXPECTED = {
    ("EMP_SA", "2026-01"): (100.0, 100.5, 0.5),
    ("EMP_SA", "2026-02"): (101.0, 100.8, -0.2),
    ("EMP_SA", "2026-03"): (103.0, 102.0, -1.0),
    ("EMP_SA", "2026-04"): (105.0, 104.0, -1.0),
    ("EMP_SA", "2026-05"): (106.0, 103.0, -3.0),
    ("EMP_SA", "2026-06"): (108.0, 102.0, -6.0),
    ("HOURS_SA", "2026-01"): (40.0, 40.0, 0.0),
    ("HOURS_SA", "2026-02"): (40.1, 40.0, -0.1),
    ("HOURS_SA", "2026-03"): (40.2, 40.1, -0.1),
    ("HOURS_SA", "2026-04"): (40.4, 40.3, -0.1),
    ("HOURS_SA", "2026-05"): (40.3, 40.0, -0.3),
    ("HOURS_SA", "2026-06"): (40.1, 40.2, 0.1),
}
OPTIONAL_NSA_KEY = ("EMP_NSA", "2026-06")
CLAIMS = {
    "employment_increased": ("withdraw", "decrease"),
    "average_hours_decreased": ("withdraw", "increase"),
    "employment_above_january": ("retain", "supported"),
}


def _norm(value: Any) -> str:
    return re.sub(r"[\s_:/-]+", " ", str(value or "").strip().casefold())


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text or _norm(text) in {"unknown", "n a", "na", "none", "null"}:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _close(value: Any, expected: float) -> bool:
    parsed = _number(value)
    return parsed is not None and math.isclose(parsed, expected, abs_tol=1e-6)


def _direction(value: float, prior: float) -> str:
    return "increase" if value > prior else "decrease" if value < prior else "flat"


def _decision_ok(value: Any, claim_id: str) -> bool:
    normalized = _norm(value)
    action, conclusion = CLAIMS[claim_id]
    if action == "withdraw":
        action_ok = any(
            term in normalized
            for term in (
                "withdraw",
                "replace",
                "refut",
                "retract",
                "no longer supported",
                "unsupported",
            )
        )
        direction_ok = (
            conclusion in normalized
            or (
                conclusion == "decrease"
                and any(term in normalized for term in ("decline", "down"))
            )
            or (
                conclusion == "increase"
                and any(term in normalized for term in ("rise", "up"))
            )
        )
        return action_ok and direction_ok
    return any(
        term in normalized
        for term in ("retain", "support", "still valid", "confirmed", "unchanged")
    )


def _nsa_exclusion_is_explained(text: str) -> bool:
    if "emp nsa" not in text or re.search(r"\b(?:not|never)\s+exclud", text):
        return False
    exclusion = bool(
        re.search(r"\bexclud\w*\b.{0,180}\b(?:trend|conclusion|comparison)", text)
        or re.search(r"\b(?:trend|conclusion|comparison)\b.{0,180}\bexclud\w*\b", text)
    )
    reason = "not seasonally adjusted" in text or any(
        term in text
        for term in (
            "no comparable",
            "not comparable",
            "missing preliminary",
            "unmatched",
        )
    )
    return exclusion and reason


def _nsa_rows_excluded(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value == 1
    if isinstance(value, list):
        return {_norm(item) for item in value} == {"emp nsa"}
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
        with (root / "revisions.csv").open(
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
    by_key = {(row["series"], row["month"]): row for row in rows}
    optional = by_key.get(OPTIONAL_NSA_KEY)
    optional_ok = optional is None or (
        _number(optional.get("preliminary")) is None
        and _close(optional.get("revised"), 109.0)
        and _number(optional.get("delta")) is None
        and _norm(optional.get("adjustment")) in {"not seasonally adjusted", "nsa"}
    )
    allowed = set(EXPECTED) | {OPTIONAL_NSA_KEY}
    integrity = (
        header == HEADER
        and len(rows) == len(by_key)
        and set(EXPECTED).issubset(by_key)
        and set(by_key).issubset(allowed)
        and optional_ok
    )
    _add(
        checks,
        "ledger_integrity",
        integrity,
        {"header": header, "row_count": len(rows)},
    )
    for index, (key, expected) in enumerate(EXPECTED.items(), start=1):
        row = by_key.get(key, {})
        detail = {
            "preliminary": _close(row.get("preliminary"), expected[0]),
            "revised": _close(row.get("revised"), expected[1]),
            "delta": _close(row.get("delta"), expected[2]),
            "adjustment": _norm(row.get("adjustment")) in {"seasonally adjusted", "sa"},
        }
        _add(checks, f"ledger_item_{index}", integrity and all(detail.values()), detail)

    state: dict[str, Any] = {}
    try:
        candidate = json.loads((root / "report_state.json").read_text(encoding="utf-8"))
        if isinstance(candidate, dict):
            state = candidate
    except Exception:
        state = {}
    vintages = state.get("vintages_retained")
    series = state.get("series_used")
    decisions = state.get("claim_decisions")
    _add(
        checks,
        "state_vintages",
        isinstance(vintages, list)
        and len(vintages) == 2
        and {_norm(value) for value in vintages} == {"preliminary", "revised"},
    )
    _add(
        checks,
        "state_series",
        isinstance(series, list)
        and len(series) == 2
        and {_norm(value) for value in series} == {"emp sa", "hours sa"},
    )
    _add(
        checks,
        "state_latest_period",
        str(state.get("latest_period") or "").strip() == "2026-06",
    )
    _add(
        checks,
        "state_claim_decisions",
        isinstance(decisions, dict)
        and set(decisions) == set(CLAIMS)
        and all(_decision_ok(decisions.get(claim_id), claim_id) for claim_id in CLAIMS),
    )
    _add(
        checks, "state_nsa_excluded", _nsa_rows_excluded(state.get("nsa_rows_excluded"))
    )

    brief_path = root / "revision_brief.md"
    brief = (
        brief_path.read_text(encoding="utf-8", errors="replace")
        if brief_path.is_file()
        else ""
    )
    normalized = _norm(brief)
    employment_series = "emp sa" in normalized or (
        "employment" in normalized and "seasonally adjusted" in normalized
    )
    hours_series = "hours sa" in normalized or (
        "hours" in normalized and "seasonally adjusted" in normalized
    )
    _add(
        checks,
        "report_vintages_series",
        "preliminary" in normalized
        and "revised" in normalized
        and employment_series
        and hours_series,
    )
    emp_reversal = (
        employment_series
        and any(term in normalized for term in ("increase", "rose", "upward"))
        and any(
            term in normalized for term in ("decrease", "falls", "decline", "downward")
        )
    )
    hours_reversal = (
        hours_series
        and any(term in normalized for term in ("decrease", "fell", "downward"))
        and any(term in normalized for term in ("increase", "rises", "upward"))
    )
    _add(
        checks,
        "report_changed_claims",
        emp_reversal
        and hours_reversal
        and any(
            term in normalized for term in ("withdraw", "replace", "refut", "no longer")
        ),
    )
    _add(
        checks,
        "report_retained_claim",
        "january" in normalized
        and any(term in normalized for term in ("above", "greater"))
        and any(
            term in normalized
            for term in ("retain", "still holds", "remains valid", "supported")
        ),
    )
    _add(checks, "report_exclusion_safety", _nsa_exclusion_is_explained(normalized))

    derived: dict[str, dict[str, str]] = {}
    if integrity:
        for series_id in ("EMP_SA", "HOURS_SA"):
            may = by_key[(series_id, "2026-05")]
            june = by_key[(series_id, "2026-06")]
            derived[series_id] = {
                "old": _direction(
                    _number(june.get("preliminary")) or 0.0,
                    _number(may.get("preliminary")) or 0.0,
                ),
                "new": _direction(
                    _number(june.get("revised")) or 0.0,
                    _number(may.get("revised")) or 0.0,
                ),
            }
    closure = (
        integrity
        and derived
        == {
            "EMP_SA": {"old": "increase", "new": "decrease"},
            "HOURS_SA": {"old": "decrease", "new": "increase"},
        }
        and isinstance(decisions, dict)
        and all(_decision_ok(decisions.get(claim_id), claim_id) for claim_id in CLAIMS)
        and _nsa_rows_excluded(state.get("nsa_rows_excluded"))
    )
    _add(checks, "analysis_closure", closure, {"derived_latest_directions": derived})
    return {
        "task": "086-revision-vintage-ledger",
        "workspace": str(root),
        "outcome_score": sum(bool(check["pass"]) for check in checks) / len(checks),
        "checks": checks,
    }
