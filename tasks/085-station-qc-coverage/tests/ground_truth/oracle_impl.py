from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path
from typing import Any


HEADER = ["station", "date", "value_c", "status", "reason"]
# The first six entries retain their historical order so diagnostic check IDs
# remain stable while the business fixture grows beyond the former six-row toy.
EXPECTED: dict[tuple[str, str], tuple[float | None, str, str]] = {
    ("ST-A", "2026-01-01"): (12.0, "usable", "valid"),
    ("ST-A", "2026-01-02"): (12.5, "usable", "duplicate"),
    ("ST-A", "2026-01-03"): (None, "excluded", "sentinel"),
    ("ST-A", "2026-01-04"): (14.0, "usable", "valid"),
    ("ST-B", "2026-01-01"): (None, "excluded", "qflag"),
    ("ST-B", "2026-01-02"): (13.0, "usable", "valid"),
    ("ST-A", "2026-01-05"): (13.5, "usable", "valid"),
    ("ST-A", "2026-01-06"): (14.5, "usable", "valid"),
    ("ST-A", "2026-01-07"): (15.0, "usable", "valid"),
    ("ST-B", "2026-01-03"): (14.0, "usable", "valid"),
    ("ST-B", "2026-01-04"): (15.0, "usable", "valid"),
    ("ST-B", "2026-01-05"): (None, "excluded", "missing"),
    ("ST-B", "2026-01-06"): (16.0, "usable", "valid"),
    ("ST-C", "2026-01-01"): (10.0, "usable", "valid"),
    ("ST-C", "2026-01-02"): (12.0, "usable", "valid"),
    ("ST-C", "2026-01-03"): (13.0, "usable", "valid"),
    ("ST-C", "2026-01-04"): (15.0, "usable", "duplicate"),
    ("ST-C", "2026-01-05"): (None, "excluded", "qflag"),
    ("ST-C", "2026-01-06"): (17.0, "usable", "valid"),
    ("ST-C", "2026-01-07"): (18.0, "usable", "valid"),
    ("ST-D", "2026-01-01"): (11.0, "usable", "valid"),
    ("ST-D", "2026-01-02"): (12.0, "usable", "preliminary"),
    ("ST-D", "2026-01-03"): (None, "excluded", "no_fallback"),
    ("ST-D", "2026-01-04"): (None, "excluded", "sentinel"),
}
STATIONS = ("ST-A", "ST-B", "ST-C", "ST-D")
VALID_DAYS = {"ST-A": 6, "ST-B": 4, "ST-C": 6, "ST-D": 2}
MEANS = {"ST-A": 13.5833333333, "ST-C": 14.1666666667}


def _norm(value: Any) -> str:
    return re.sub(r"[\s_:/-]+", " ", str(value or "").strip().casefold())


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _close(value: Any, expected: float, tolerance: float = 1e-5) -> bool:
    parsed = _number(value)
    return parsed is not None and math.isclose(parsed, expected, abs_tol=tolerance)


def _status(value: Any) -> str | None:
    normalized = _norm(value)
    if normalized in {"included", "valid", "usable", "accepted", "kept", "pass"}:
        return "usable"
    if normalized in {
        "excluded",
        "quarantined",
        "invalid",
        "rejected",
        "omitted",
        "failed",
    }:
        return "excluded"
    return None


def _cause_ok(reason: str, cause: str) -> bool:
    if cause == "valid":
        return True
    aliases = {
        "duplicate": ("duplicate", "final wins", "final selected"),
        "sentinel": ("sentinel", "9999"),
        "qflag": ("qflag", "quality flag", "flag x", "flagged"),
        "missing": ("missing", "blank", "no value"),
        "preliminary": ("prelim", "no final"),
        "no_fallback": ("no fallback", "flagged final", "final failed"),
    }
    return any(alias in reason for alias in aliases[cause])


def _excluded_value_ok(value: Any, key: tuple[str, str]) -> bool:
    parsed = _number(value)
    if parsed is None:
        return True
    allowed = {
        ("ST-A", "2026-01-03"): {-999.9},
        ("ST-B", "2026-01-01"): {12.0},
        ("ST-C", "2026-01-05"): {16.0},
        ("ST-D", "2026-01-03"): {13.0},
        ("ST-D", "2026-01-04"): {-9999.0},
    }
    return any(
        math.isclose(parsed, item, abs_tol=1e-5) for item in allowed.get(key, set())
    )


def _mapping_close(value: Any, expected: dict[str, float]) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == set(expected)
        and all(_close(value.get(key), number) for key, number in expected.items())
    )


def _string_set(value: Any) -> set[str] | None:
    return {str(item).strip() for item in value} if isinstance(value, list) else None


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
        with (root / "qc_records.csv").open(
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
    by_key = {(row["station"], row["date"]): row for row in rows}
    integrity = (
        header == HEADER
        and len(rows) == len(by_key) == len(EXPECTED)
        and set(by_key) == set(EXPECTED)
    )
    _add(
        checks,
        "ledger_integrity",
        integrity,
        {"header": header, "row_count": len(rows)},
    )

    for index, (key, (expected_value, expected_status, cause)) in enumerate(
        EXPECTED.items(), start=1
    ):
        row = by_key.get(key, {})
        value_ok = (
            _excluded_value_ok(row.get("value_c"), key)
            if expected_value is None
            else _close(row.get("value_c"), expected_value)
        )
        detail = {
            "value": value_ok,
            "status": _status(row.get("status")) == expected_status,
            "cause": _cause_ok(_norm(row.get("reason")), cause),
        }
        # Row correctness and closed-set integrity are separate business
        # outcomes. Extra invented dates must not make every correct source row
        # appear wrong a second time.
        _add(checks, f"ledger_item_{index}", all(detail.values()), detail)

    state: dict[str, Any] = {}
    try:
        candidate = json.loads((root / "coverage.json").read_text(encoding="utf-8"))
        if isinstance(candidate, dict):
            state = candidate
    except Exception:
        state = {}
    coverage_expected = {station: days / 7 for station, days in VALID_DAYS.items()}
    _add(checks, "state_window_days", state.get("window_days") == 7)
    _add(
        checks, "state_valid_days", _mapping_close(state.get("valid_days"), VALID_DAYS)
    )
    _add(
        checks,
        "state_coverage",
        _mapping_close(state.get("coverage"), coverage_expected),
    )
    _add(
        checks,
        "state_qualified",
        _string_set(state.get("qualified_stations")) == {"ST-A", "ST-C"},
    )
    _add(
        checks,
        "state_excluded",
        _string_set(state.get("excluded_stations")) == {"ST-B", "ST-D"},
    )
    _add(checks, "state_means", _mapping_close(state.get("mean_c"), MEANS))

    note_path = root / "qc_note.md"
    note = (
        note_path.read_text(encoding="utf-8", errors="replace")
        if note_path.is_file()
        else ""
    )
    normalized = _norm(note)
    _add(
        checks,
        "report_duplicate",
        "duplicate" in normalized
        and "final" in normalized
        and "prelim" in normalized
        and "st d" in normalized
        and any(
            term in normalized for term in ("fallback", "fall back", "falling back")
        ),
    )
    _add(
        checks,
        "report_exclusions",
        "9999" in normalized
        and ("qflag" in normalized or "quality flag" in normalized)
        and any(term in normalized for term in ("blank", "missing", "no value")),
    )
    fahrenheit_explained = "fahrenheit" in normalized or bool(
        re.search(r"\bf\b.{0,40}\b32\b.{0,40}\b5\s*9\b", normalized)
    )
    tenths_explained = any(
        term in normalized
        for term in ("tenths c", "tenths of c", "tenths celsius", "value 10")
    )
    celsius_explained = "celsius" in normalized or bool(
        re.search(r"\bc\b.{0,35}(?:no conversion|unchanged)", normalized)
    )
    _add(
        checks,
        "report_units",
        fahrenheit_explained and tenths_explained and celsius_explained,
    )
    threshold_explained = any(
        term in normalized for term in ("5 of 7", "five of seven", "5 usable")
    )
    station_outcomes = all(
        station.casefold().replace("-", " ") in normalized for station in STATIONS
    ) and all(term in normalized for term in ("qualified", "excluded"))
    _add(
        checks,
        "report_coverage_safety",
        station_outcomes
        and threshold_explained
        and any(
            term in normalized
            for term in ("verify", "verification", "reconcile", "checked")
        ),
    )

    usable_by_station = {station: 0 for station in STATIONS}
    values_by_station: dict[str, list[float]] = {station: [] for station in STATIONS}
    for (station, _date), row in by_key.items():
        if station in usable_by_station and _status(row.get("status")) == "usable":
            number = _number(row.get("value_c"))
            if number is not None:
                usable_by_station[station] += 1
                values_by_station[station].append(number)
    derived_means = {
        station: sum(values_by_station[station]) / len(values_by_station[station])
        for station in ("ST-A", "ST-C")
        if values_by_station[station]
    }
    closure = (
        integrity
        and usable_by_station == VALID_DAYS
        and _mapping_close(state.get("valid_days"), VALID_DAYS)
        and _mapping_close(state.get("coverage"), coverage_expected)
        and _mapping_close(state.get("mean_c"), derived_means)
    )
    _add(
        checks,
        "cross_artifact_closure",
        closure,
        {"valid_days": usable_by_station, "mean_c": derived_means},
    )
    return {
        "task": "085-station-qc-coverage",
        "workspace": str(root),
        "outcome_score": sum(bool(check["pass"]) for check in checks) / len(checks),
        "checks": checks,
    }
