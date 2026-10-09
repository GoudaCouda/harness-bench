from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[2]
GROUND_TRUTH = TASK_DIR / "tests" / "ground_truth" / "ground_truth.json"

INDEX_HEADER = [
    "source_path",
    "target_path",
    "record_type",
    "record_id",
    "status",
]
REJECT_HEADER = ["source_path", "error_type", "details"]


def _add(
    checks: list[dict[str, Any]],
    check_id: str,
    label: str,
    passed: bool,
    weight: float,
    detail: Any = None,
) -> None:
    checks.append(
        {
            "id": check_id,
            "label": label,
            "pass": bool(passed),
            "weight": weight,
            "detail": None if passed else detail,
        }
    )


def _read_csv(
    path: Path,
) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = [
            {key: (value or "").strip() for key, value in row.items()} for row in reader
        ]
        return list(reader.fieldnames or []), rows


def _record_matches(
    actual: Any,
    expected: dict[str, Any],
) -> bool:
    if not isinstance(actual, dict):
        return False
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if isinstance(expected_value, float) and isinstance(
            actual_value,
            str,
        ):
            try:
                actual_value = float(actual_value)
            except ValueError:
                pass
        if actual_value != expected_value:
            return False
    return set(actual) <= set(expected) | {"source_path"}


def _normalized_error_type(value: str) -> str:
    aliases = {
        "unknown_extension": "unsupported_extension",
        "unsupported_file_type": "unsupported_extension",
        "missing_fields": "missing_required_field",
        "missing_required_fields": "missing_required_field",
        "duplicate_id": "duplicate_record_id",
        "duplicate_record": "duplicate_record_id",
    }
    normalized = value.strip().lower()
    return aliases.get(normalized, normalized)


def _index_key(row: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(row.get(key, "")).strip() for key in INDEX_HEADER)


def _index_identity(row: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        str(row.get(key, "")).strip()
        for key in ("source_path", "target_path", "record_type", "record_id")
    )


def _index_status_matches(
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> bool:
    status = str(actual.get("status", "")).strip().casefold()
    expected_status = str(expected.get("status", "")).strip().casefold()
    return status in {expected_status, "success"}


def _reject_key(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("source_path", "")).strip(),
        _normalized_error_type(str(row.get("error_type", ""))),
    )


def _is_sorted_by_source(rows: list[dict[str, str]]) -> bool:
    paths = [row.get("source_path", "") for row in rows]
    return paths == sorted(paths)


def score_workspace(workspace: Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    truth = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []

    output_dir = root / "normalized"
    actual_names = (
        sorted(path.name for path in output_dir.glob("*.json"))
        if output_dir.is_dir()
        else []
    )
    expected_names = sorted(truth["outputs"])
    normalized_weight = 0.40 / len(expected_names)
    for name, expected in truth["outputs"].items():
        path = output_dir / name
        try:
            actual = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            actual = None
            detail: Any = str(exc)
        else:
            detail = actual
        _add(
            checks,
            f"content_{name}",
            f"{name} contains the normalized source record",
            _record_matches(actual, expected),
            normalized_weight,
            detail,
        )
    _add(
        checks,
        "file_set",
        "normalized file set is closed: no missing or extra records",
        actual_names == expected_names,
        0.05,
        {
            "missing": sorted(set(expected_names) - set(actual_names)),
            "extra": sorted(set(actual_names) - set(expected_names)),
        },
    )

    index_path = root / "index.csv"
    try:
        index_header, index_rows = _read_csv(index_path)
    except Exception as exc:
        index_header, index_rows = [], []
        index_error: Any = str(exc)
    else:
        index_error = None
    _add(
        checks,
        "index_header",
        "index.csv uses the published header",
        index_header == INDEX_HEADER,
        0.03,
        index_error or index_header,
    )
    actual_index = Counter(_index_identity(row) for row in index_rows)
    expected_index = Counter(_index_identity(row) for row in truth["index_rows"])
    actual_by_identity = {
        _index_identity(row): row
        for row in index_rows
        if actual_index[_index_identity(row)] == 1
    }
    index_row_weight = 0.20 / len(truth["index_rows"])
    for expected_row in truth["index_rows"]:
        key = _index_identity(expected_row)
        _add(
            checks,
            f"index_{expected_row['record_id']}",
            f"index contains {expected_row['record_id']}",
            actual_index[key] >= expected_index[key]
            and _index_status_matches(actual_by_identity.get(key, {}), expected_row),
            index_row_weight,
            expected_row,
        )
    index_closed = actual_index == expected_index and all(
        _index_status_matches(actual_by_identity.get(_index_identity(row), {}), row)
        for row in truth["index_rows"]
    )
    index_sorted = _is_sorted_by_source(index_rows)
    _add(
        checks,
        "index_closed_and_sorted",
        "index has exactly the successful rows in source-path order",
        index_closed and index_sorted,
        0.05,
        {
            "closed": index_closed,
            "sorted": index_sorted,
            "rows": len(index_rows),
        },
    )
    _add(
        checks,
        "index_rows",
        "all exact index rows are present without extras",
        index_closed and index_sorted,
        0.0,
        index_rows,
    )

    reject_path = root / "reject_ledger.csv"
    try:
        reject_header, reject_rows = _read_csv(reject_path)
    except Exception as exc:
        reject_header, reject_rows = [], []
        reject_error: Any = str(exc)
    else:
        reject_error = None
    _add(
        checks,
        "reject_header",
        "reject_ledger.csv uses the published header",
        reject_header == REJECT_HEADER,
        0.03,
        reject_error or reject_header,
    )
    actual_rejects = Counter(_reject_key(row) for row in reject_rows)
    expected_rejects = Counter(_reject_key(row) for row in truth["reject_rows"])
    reject_row_weight = 0.15 / len(truth["reject_rows"])
    seen: Counter[tuple[str, str]] = Counter()
    for index, expected_row in enumerate(truth["reject_rows"], start=1):
        key = _reject_key(expected_row)
        seen[key] += 1
        _add(
            checks,
            f"reject_{index:02d}",
            f"reject ledger contains {key[0]} as {key[1]}",
            actual_rejects[key] >= seen[key],
            reject_row_weight,
            expected_row,
        )
    rejects_closed = actual_rejects == expected_rejects
    rejects_sorted = _is_sorted_by_source(reject_rows)
    _add(
        checks,
        "rejects_closed_and_sorted",
        "reject ledger is an exact multiset in source-path order",
        rejects_closed and rejects_sorted,
        0.04,
        {
            "closed": rejects_closed,
            "sorted": rejects_sorted,
            "rows": len(reject_rows),
        },
    )
    _add(
        checks,
        "reject_rows",
        "all expected rejects are present without extras",
        rejects_closed and rejects_sorted,
        0.0,
        reject_rows,
    )

    summary_path = root / "batch_summary.json"
    try:
        parsed_summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary = parsed_summary if isinstance(parsed_summary, dict) else {}
    except Exception as exc:
        summary = {}
        summary_error: Any = str(exc)
    else:
        summary_error = None
    expected_summary = truth["summary"]
    summary_checks = {
        "success_count": (
            summary.get("success_count") == expected_summary["success_count"]
        ),
        "reject_count": (
            summary.get("reject_count") == expected_summary["reject_count"]
        ),
        "by_type": summary.get("by_type") == expected_summary["by_type"],
        "closed_schema": (set(summary) == {"success_count", "reject_count", "by_type"}),
    }
    for key, passed in summary_checks.items():
        _add(
            checks,
            f"summary_{key}",
            f"batch summary {key} matches the output ledgers",
            passed,
            0.0125,
            summary_error or summary.get(key),
        )

    total_weight = sum(float(check["weight"]) for check in checks)
    earned = sum(float(check["weight"]) for check in checks if check["pass"])
    score = earned / total_weight if total_weight else 0.0
    return {
        "task": "051-smallfile-batch-reject-ledger",
        "workspace": str(root),
        "checks": checks,
        "outcome_score": round(score, 4),
    }
