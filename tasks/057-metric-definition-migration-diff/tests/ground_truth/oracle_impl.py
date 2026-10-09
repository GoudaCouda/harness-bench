from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


EXPECTED_DIFF = [
    {
        "metric_name": "activation_rate",
        "old_value": "0.4000",
        "new_value": "0.4500",
        "absolute_diff": "0.0500",
        "relative_diff": "0.1250",
        "expected_direction": "increase",
        "classification": "expected_definition_change",
    },
    {
        "metric_name": "arr",
        "old_value": "100000.0000",
        "new_value": "92000.0000",
        "absolute_diff": "8000.0000",
        "relative_diff": "-0.0800",
        "expected_direction": "decrease",
        "classification": "expected_definition_change",
    },
    {
        "metric_name": "gross_margin",
        "old_value": "0.5500",
        "new_value": "",
        "absolute_diff": "",
        "relative_diff": "",
        "expected_direction": "unknown",
        "classification": "requires_review",
    },
    {
        "metric_name": "retention_rate",
        "old_value": "0.7000",
        "new_value": "0.6900",
        "absolute_diff": "0.0100",
        "relative_diff": "-0.0143",
        "expected_direction": "unknown",
        "classification": "unexpected_regression",
    },
    {
        "metric_name": "support_sla",
        "old_value": "0.9500",
        "new_value": "0.9510",
        "absolute_diff": "0.0010",
        "relative_diff": "0.0011",
        "expected_direction": "stable",
        "classification": "no_material_change",
    },
]
EXPECTED_REGRESSIONS = [
    {
        "metric_name": "retention_rate",
        "bad_field": "old_cohort_users",
        "policy_clause": "retention must use new_cohort_users after migration",
        "severity": "high",
    },
]


def _add(
    checks: list[dict[str, Any]],
    cid: str,
    ok: bool,
    weight: float,
    detail: str | None = None,
) -> None:
    checks.append(
        {
            "id": cid,
            "pass": bool(ok),
            "weight": weight,
            "detail": None if ok else detail,
        }
    )


def _rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), [
            {k: (v or "").strip() for k, v in row.items()} for row in r
        ]


def _sorted_rows(rows: list[dict[str, str]], keys: list[str]) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: tuple(row.get(key, "") for key in keys))


def _norm(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")


def _direction_matches(actual: str, expected: str) -> bool:
    actual_n = _norm(actual)
    expected_n = _norm(expected)
    if expected_n == "unknown" and not actual_n:
        return True
    aliases = {
        "increase": ["increase", "increase possible", "up"],
        "decrease": ["decrease", "decrease or flat", "down"],
        "stable": [
            "stable",
            "flat",
            "unchanged",
            "unchanged definition",
            "no material change",
        ],
        "unknown": [
            "unknown",
            "requires review",
            "requires comparison",
            "missing",
            "blank",
        ],
    }
    return actual_n == expected_n or any(
        alias in actual_n for alias in aliases.get(expected_n, [])
    )


def _values_match(row: dict[str, str], exp: dict[str, str]) -> bool:
    for key in ["old_value", "new_value", "absolute_diff", "relative_diff"]:
        if str(row.get(key, "")).strip() != exp[key]:
            return False
    return True


def score_workspace(workspace: str | Path) -> dict[str, Any]:
    w = Path(workspace).resolve()
    checks: list[dict[str, Any]] = []
    for rel in [
        "old_metric_definitions.md",
        "new_metric_definitions.md",
        "dashboard_before.csv",
        "dashboard_after.csv",
        "migration_policy.md",
    ]:
        _add(
            checks,
            f"fixture_present_{rel}",
            (w / rel).is_file(),
            0.0,
            f"missing {rel}",
        )

    diff = w / "metric_migration_diff.csv"
    reg = w / "regression_ledger.csv"
    summary = w / "migration_summary.json"
    caveats = w / "caveats.md"
    diff_rows: list[dict[str, str]] = []
    summary_data: dict[str, Any] = {}
    _add(checks, "diff_exists", diff.is_file(), 0.06, "missing diff")
    diff_values_ok = False
    if diff.is_file():
        try:
            header, rows = _rows(diff)
            diff_rows = rows
            _add(
                checks,
                "diff_header",
                header
                == [
                    "metric_name",
                    "old_value",
                    "new_value",
                    "absolute_diff",
                    "relative_diff",
                    "expected_direction",
                    "classification",
                ],
                0.06,
                f"got {header}",
            )
            by_metric = {row.get("metric_name", ""): row for row in rows}
            expected_metrics = {row["metric_name"] for row in EXPECTED_DIFF}
            coverage_ok = (
                len(rows) == len(by_metric) == len(expected_metrics)
                and set(by_metric) == expected_metrics
            )
            value_hits = 0
            class_hits = 0
            direction_hits = 0
            for exp in EXPECTED_DIFF:
                row = by_metric.get(exp["metric_name"], {})
                values_match = _values_match(row, exp)
                classification_matches = (
                    row.get("classification", "").strip() == exp["classification"]
                )
                direction_matches = _direction_matches(
                    row.get("expected_direction", ""), exp["expected_direction"]
                )
                if values_match:
                    value_hits += 1
                if classification_matches:
                    class_hits += 1
                if direction_matches:
                    direction_hits += 1
                metric = exp["metric_name"]
                _add(
                    checks,
                    f"diff_values_{metric}",
                    values_match,
                    0.16 / len(EXPECTED_DIFF),
                    f"got {row}",
                )
                _add(
                    checks,
                    f"diff_classification_{metric}",
                    classification_matches,
                    0.12 / len(EXPECTED_DIFF),
                    f"got {row.get('classification', '')!r}",
                )
                _add(
                    checks,
                    f"diff_direction_{metric}",
                    direction_matches,
                    0.04 / len(EXPECTED_DIFF),
                    (
                        f"got {row.get('expected_direction', '')!r}; "
                        f"expected {exp['expected_direction']!r}"
                    ),
                )
            _add(checks, "diff_coverage", coverage_ok, 0.08, f"got {sorted(by_metric)}")
            diff_values_ok = value_hits == len(EXPECTED_DIFF)
            _add(
                checks,
                "diff_values_summary",
                diff_values_ok,
                0.0,
                f"hits {value_hits}/{len(EXPECTED_DIFF)}",
            )
            _add(
                checks,
                "diff_classifications_summary",
                class_hits == len(EXPECTED_DIFF),
                0.0,
                f"hits {class_hits}/{len(EXPECTED_DIFF)}",
            )
            _add(
                checks,
                "diff_directions_summary",
                direction_hits == len(EXPECTED_DIFF),
                0.0,
                f"hits {direction_hits}/{len(EXPECTED_DIFF)}",
            )
            classes = {r.get("metric_name"): r.get("classification") for r in rows}
            _add(
                checks,
                "classification_distinguishes_expected_vs_regression",
                classes.get("arr") == "expected_definition_change"
                and classes.get("retention_rate") == "unexpected_regression",
                0.08,
                f"got {classes}",
            )
        except Exception as exc:
            _add(checks, "diff_parseable", False, 0.30, str(exc))
    else:
        for cid, weight in [
            ("diff_header", 0.06),
            ("diff_coverage", 0.08),
            ("classification_distinguishes_expected_vs_regression", 0.08),
        ]:
            _add(checks, cid, False, weight, "missing")
        for exp in EXPECTED_DIFF:
            metric = exp["metric_name"]
            _add(
                checks,
                f"diff_values_{metric}",
                False,
                0.16 / len(EXPECTED_DIFF),
                "missing",
            )
            _add(
                checks,
                f"diff_classification_{metric}",
                False,
                0.12 / len(EXPECTED_DIFF),
                "missing",
            )
            _add(
                checks,
                f"diff_direction_{metric}",
                False,
                0.04 / len(EXPECTED_DIFF),
                "missing",
            )

    _add(checks, "regression_exists", reg.is_file(), 0.05, "missing regression ledger")
    if reg.is_file():
        try:
            header, rows = _rows(reg)
            _add(checks, "regression_parseable", True, 0.0)
            _add(
                checks,
                "regression_header",
                header == ["metric_name", "bad_field", "policy_clause", "severity"],
                0.05,
                f"got {header}",
            )
            retention_rows = [
                row for row in rows if row.get("metric_name") == "retention_rate"
            ]
            required_ok = any(
                "old_cohort_users" in row.get("bad_field", "")
                and row.get("severity", "").strip().lower() == "high"
                and "new_cohort_users" in row.get("policy_clause", "")
                for row in retention_rows
            )
            no_extra = len(rows) == len(retention_rows) == 1
            _add(checks, "regression_required", required_ok, 0.10, f"got {rows}")
            _add(checks, "regression_no_extra", no_extra, 0.04, f"got {rows}")
        except Exception as exc:
            _add(checks, "regression_parseable", False, 0.10, str(exc))
    else:
        _add(checks, "regression_parseable", False, 0.0, "missing")
        _add(checks, "regression_header", False, 0.05, "missing")
        _add(checks, "regression_required", False, 0.10, "missing")
        _add(checks, "regression_no_extra", False, 0.04, "missing")

    _add(checks, "summary_exists", summary.is_file(), 0.05, "missing summary")
    if summary.is_file():
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
            summary_data = data if isinstance(data, dict) else {}
            expected = {
                "total_metrics": 5,
                "expected_definition_change_count": 2,
                "unexpected_regression_count": 1,
                "no_material_change_count": 1,
                "requires_review_count": 1,
                "largest_relative_diff_metric": "activation_rate",
            }
            for key, expected_value in expected.items():
                _add(
                    checks,
                    f"summary_{key}",
                    isinstance(data, dict) and data.get(key) == expected_value,
                    0.12 / len(expected),
                    f"got {data.get(key) if isinstance(data, dict) else data!r}",
                )
            _add(
                checks,
                "summary_exact",
                data == expected,
                0.0,
                f"got {data}",
            )
        except Exception as exc:
            _add(checks, "summary_parseable", False, 0.10, str(exc))
    else:
        expected_summary_keys = [
            "total_metrics",
            "expected_definition_change_count",
            "unexpected_regression_count",
            "no_material_change_count",
            "requires_review_count",
            "largest_relative_diff_metric",
        ]
        for key in expected_summary_keys:
            _add(
                checks,
                f"summary_{key}",
                False,
                0.12 / len(expected_summary_keys),
                "missing",
            )
        _add(checks, "summary_exact", False, 0.0, "missing")

    submitted_classes: dict[str, int] = {}
    for row in diff_rows:
        classification = str(row.get("classification") or "").strip()
        submitted_classes[classification] = submitted_classes.get(classification, 0) + 1
    relative_candidates: list[tuple[float, str]] = []
    for row in diff_rows:
        raw_relative = str(row.get("relative_diff") or "").strip()
        if not raw_relative:
            continue
        try:
            relative_candidates.append(
                (abs(float(raw_relative)), str(row.get("metric_name") or ""))
            )
        except ValueError:
            continue
    submitted_largest = (
        sorted(relative_candidates, key=lambda item: (-item[0], item[1]))[0][1]
        if relative_candidates
        else None
    )
    summary_reconciles = bool(
        diff_rows
        and summary_data
        and summary_data.get("total_metrics") == len(diff_rows)
        and summary_data.get("expected_definition_change_count")
        == submitted_classes.get("expected_definition_change", 0)
        and summary_data.get("unexpected_regression_count")
        == submitted_classes.get("unexpected_regression", 0)
        and summary_data.get("no_material_change_count")
        == submitted_classes.get("no_material_change", 0)
        and summary_data.get("requires_review_count")
        == submitted_classes.get("requires_review", 0)
        and summary_data.get("largest_relative_diff_metric") == submitted_largest
    )
    _add(
        checks,
        "summary_reconciles_diff",
        summary_reconciles,
        0.0,
        f"classes={submitted_classes}, largest={submitted_largest}",
    )

    _add(checks, "caveats_exists", caveats.is_file(), 0.03, "missing caveats")
    if caveats.is_file():
        text = caveats.read_text(encoding="utf-8", errors="replace").lower()
        _add(
            checks,
            "caveats_required",
            all(
                term in text
                for term in [
                    "arr",
                    "activation",
                    "non-comparable",
                    "retention",
                    "unexpected regression",
                ]
            ),
            0.06,
            "missing migration caveats",
        )
    else:
        _add(checks, "caveats_required", False, 0.06, "missing")

    total = sum(c["weight"] for c in checks)
    score = round(sum(c["weight"] for c in checks if c["pass"]) / total, 4)
    return {
        "task": "057-metric-definition-migration-diff",
        "workspace": str(w),
        "checks": checks,
        "outcome_score": score,
        "score": score,
    }
