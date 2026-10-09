from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


TASK = Path(__file__).resolve().parents[2]
TRUTH = json.loads(
    (TASK / "tests" / "ground_truth" / "ground_truth.json").read_text(encoding="utf-8")
)
HEADER = ["state", "county", "year", "variable", "estimate", "moe", "status"]
WEIGHTS = {
    "observed_panel": 0.30,
    "change_analysis": 0.25,
    "incomplete_evidence": 0.15,
    "method_handoff": 0.10,
    "panel_integrity": 0.10,
    "cross_artifact_closure": 0.10,
}


def _close(value: Any, expected: float, tolerance: float = 1e-6) -> bool:
    try:
        return abs(float(value) - expected) <= tolerance
    except (TypeError, ValueError):
        return False


def _read_panel(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [
            {key: str(value or "").strip() for key, value in row.items() if key}
            for row in reader
        ]
        return list(reader.fieldnames or []), rows


def _normalized(value: Any) -> str:
    return " ".join(str(value or "").casefold().replace("_", " ").split())


def _observed(value: Any) -> bool:
    return _normalized(value) in {"observed", "ok", "valid", "complete"}


def _suppressed(value: Any) -> bool:
    return _normalized(value) in {
        "suppressed",
        "source suppressed",
        "not published",
        "unavailable suppressed",
    }


def _method_maps_variables(method: str) -> bool:
    low = method.casefold()
    return all(value in low for value in ("p001", "2024", "p101", "2025"))


def _variable_ok(row: dict[str, str], expected: dict[str, str], method: str) -> bool:
    value = _normalized(row.get("variable"))
    if value == _normalized(expected["variable"]):
        return True
    return value in {
        "population",
        "population estimate",
        "resident population estimate",
    } and _method_maps_variables(method)


def _observed_row_ok(
    row: dict[str, str], expected: dict[str, str], method: str
) -> bool:
    return bool(
        all(row.get(key) == expected[key] for key in ("state", "county", "year"))
        and _variable_ok(row, expected, method)
        and _close(row.get("estimate"), float(expected["estimate"]))
        and _close(row.get("moe"), float(expected["moe"]))
        and _observed(row.get("status"))
    )


def _suppressed_row_ok(
    row: dict[str, str], expected: dict[str, str], method: str
) -> bool:
    return bool(
        all(row.get(key) == expected[key] for key in ("state", "county", "year"))
        and _variable_ok(row, expected, method)
        and not row.get("estimate")
        and not row.get("moe")
        and _suppressed(row.get("status"))
    )


def _change_rows(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for item in value:
        if not isinstance(item, dict):
            continue
        state = str(item.get("state") or "").strip()
        county = str(item.get("county") or "").strip()
        if state == "06" and county and county not in rows:
            rows[county] = item
    return rows


def _change_item_ok(item: dict[str, Any], expected: list[float]) -> bool:
    old, new, change, percent = expected
    return bool(
        _close(item.get("2024_estimate"), old)
        and _close(item.get("2025_estimate"), new)
        and _close(item.get("change"), change)
        and _close(item.get("percent_change"), percent)
        and _normalized(item.get("status"))
        in {"comparable", "complete", "observed", "observed pair"}
    )


def _county_set(value: Any) -> set[str] | None:
    if not isinstance(value, list):
        return None
    counties: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        county = text.rsplit("-", 1)[-1]
        if not county:
            return None
        counties.add(county)
    return counties


def _comparable_counties_ok(value: Any, counties: set[str]) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value == len(counties)
    return _county_set(value) == counties


def _concept(text: str, alternatives: tuple[str, ...]) -> bool:
    low = _normalized(text)
    return any(value in low for value in alternatives)


def _dynamic_closure(
    rows: list[dict[str, str]], analysis: dict[str, Any]
) -> tuple[bool, dict[str, Any]]:
    requested = len(rows)
    observed = sum(_observed(row.get("status")) for row in rows)
    by_county: dict[str, dict[str, dict[str, str]]] = {}
    for row in rows:
        by_county.setdefault(row.get("county", ""), {})[row.get("year", "")] = row
    comparable: dict[str, tuple[float, float]] = {}
    incomplete: list[str] = []
    for county, years in by_county.items():
        old = years.get("2024")
        new = years.get("2025")
        if (
            old
            and new
            and _observed(old.get("status"))
            and _observed(new.get("status"))
        ):
            try:
                comparable[county] = (float(old["estimate"]), float(new["estimate"]))
            except (KeyError, ValueError):
                incomplete.append(county)
        else:
            incomplete.append(county)
    submitted_changes = _change_rows(analysis.get("changes"))
    dynamic_changes_ok = set(submitted_changes) == set(comparable)
    if dynamic_changes_ok:
        for county, (old, new) in comparable.items():
            expected = [old, new, new - old, (new - old) / old * 100]
            if not _change_item_ok(submitted_changes[county], expected):
                dynamic_changes_ok = False
                break
    submitted_incomplete = analysis.get("incomplete_counties")
    incomplete_ok = _county_set(submitted_incomplete) == set(incomplete)
    counts_ok = bool(
        analysis.get("requested_rows") == requested
        and analysis.get("observed_rows") == observed
        and _comparable_counties_ok(
            analysis.get("comparable_counties"), set(comparable)
        )
    )
    return (
        counts_ok and incomplete_ok and dynamic_changes_ok,
        {
            "requested_rows": requested,
            "observed_rows": observed,
            "comparable": sorted(comparable),
            "incomplete": sorted(incomplete),
        },
    )


def score_workspace(workspace: Path) -> dict[str, Any]:
    workspace = Path(workspace).resolve()
    panel_path = workspace / "panel.csv"
    analysis_path = workspace / "analysis.json"
    method_path = workspace / "method.md"

    header: list[str] = []
    rows: list[dict[str, str]] = []
    panel_parseable = False
    try:
        header, rows = _read_panel(panel_path)
        panel_parseable = True
    except Exception:
        pass

    method = (
        method_path.read_text(encoding="utf-8", errors="replace")
        if method_path.is_file()
        else ""
    )
    by_key: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        key = (row.get("state", ""), row.get("county", ""), row.get("year", ""))
        by_key.setdefault(key, []).append(row)

    observed_failures: list[str] = []
    suppressed_failures: list[str] = []
    for expected in TRUTH["rows"]:
        key = (expected["state"], expected["county"], expected["year"])
        candidates = by_key.get(key, [])
        label = "/".join(key)
        if expected["status"] == "observed":
            if len(candidates) != 1 or not _observed_row_ok(
                candidates[0], expected, method
            ):
                observed_failures.append(label)
        elif len(candidates) != 1 or not _suppressed_row_ok(
            candidates[0], expected, method
        ):
            suppressed_failures.append(label)
    observed_panel = not observed_failures

    target_keys = {(row["state"], row["county"], row["year"]) for row in TRUTH["rows"]}
    actual_keys = [
        (row.get("state", ""), row.get("county", ""), row.get("year", ""))
        for row in rows
    ]
    panel_integrity = bool(
        panel_parseable
        and header == HEADER
        and len(rows) == len(target_keys)
        and len(set(actual_keys)) == len(actual_keys)
        and set(actual_keys) == target_keys
    )

    analysis: dict[str, Any] = {}
    analysis_parseable = False
    try:
        value = json.loads(analysis_path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            analysis = value
            analysis_parseable = True
    except Exception:
        pass
    geography_key = analysis.get("geography_key")
    key_ok = bool(
        isinstance(geography_key, list)
        and [_normalized(value) for value in geography_key] == ["state", "county"]
    )
    changes = _change_rows(analysis.get("changes"))
    expected_changes = TRUTH["changes"]
    changes_ok = bool(
        set(changes) == set(expected_changes)
        and all(
            _change_item_ok(changes[county], expected)
            for county, expected in expected_changes.items()
        )
    )
    aggregate_ok = bool(
        analysis.get("requested_rows") == 8
        and analysis.get("observed_rows") == 7
        and _comparable_counties_ok(
            analysis.get("comparable_counties"), set(expected_changes)
        )
        and analysis.get("moe_not_aggregated_as_estimate") is True
    )
    change_analysis = analysis_parseable and key_ok and changes_ok and aggregate_ok
    incomplete_list = analysis.get("incomplete_counties")
    incomplete_evidence = bool(
        not suppressed_failures
        and isinstance(incomplete_list, list)
        and _county_set(incomplete_list) == set(TRUTH["incomplete_counties"])
        and "007" not in changes
    )

    method_handoff = bool(
        len(method.strip()) >= 160
        and _concept(method, ("stable", "state and county", "state/county"))
        and _method_maps_variables(method)
        and _concept(method, ("margin of error", "margin-of-error", "moe"))
        and _concept(method, ("suppress", "not published"))
        and _concept(
            method,
            ("no imputation", "not imputed", "without imputation", "avoid imputing"),
        )
        and _concept(method, ("state total", "aggregate"))
        and _concept(method, ("same-name", "same name", "display name"))
        and _concept(method, ("reparse", "reparsed", "reconcile", "validated"))
    )
    closure_ok, closure_detail = _dynamic_closure(rows, analysis)
    cross_artifact_closure = bool(panel_parseable and analysis_parseable and closure_ok)

    results = {
        "observed_panel": observed_panel,
        "change_analysis": change_analysis,
        "incomplete_evidence": incomplete_evidence,
        "method_handoff": method_handoff,
        "panel_integrity": panel_integrity,
        "cross_artifact_closure": cross_artifact_closure,
    }
    details = {
        "observed_panel": {"missing_or_wrong": observed_failures},
        "change_analysis": {
            "geography_key": key_ok,
            "changes": changes_ok,
            "aggregate": aggregate_ok,
        },
        "incomplete_evidence": {"missing_or_wrong": suppressed_failures},
        "method_handoff": None,
        "panel_integrity": {"row_count": len(rows), "keys": actual_keys},
        "cross_artifact_closure": closure_detail,
    }
    checks = [
        {
            "id": case_id,
            "pass": passed,
            "weight": WEIGHTS[case_id],
            "detail": details[case_id],
        }
        for case_id, passed in results.items()
    ]
    score = sum(WEIGHTS[case_id] for case_id, passed in results.items() if passed)
    return {
        "task": "083-census-geography-align",
        "workspace": str(workspace),
        "outcome_score": round(score, 4),
        "checks": checks,
    }
