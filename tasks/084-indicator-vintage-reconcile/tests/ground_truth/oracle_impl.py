from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path
from typing import Any


HEADER = ["country", "year", "indicator", "unit", "value", "revision_from_prior"]
EXPECTED = {
    ("Aster", "2023"): ("GDPCON15", "constant 2015 credits", 502.0, 2.0),
    ("Aster", "2024"): ("GDPCON15", "constant 2015 credits", 510.0, 5.0),
    ("Aster", "2025"): ("GDPCON15", "constant 2015 credits", 525.0, None),
    ("Boron", "2023"): ("GDPCON15", "constant 2015 credits", 482.0, 2.0),
    ("Boron", "2024"): ("GDPCON15", "constant 2015 credits", 490.0, -5.0),
    ("Boron", "2025"): ("GDPCON15", "constant 2015 credits", 530.0, None),
    ("Cygnus", "2023"): ("GDPCON15", "constant 2015 credits", 518.0, -2.0),
    ("Cygnus", "2024"): ("GDPCON15", "constant 2015 credits", 538.0, 3.0),
    ("Cygnus", "2025"): ("GDPCON15", "constant 2015 credits", 540.0, None),
}


def _norm(value: Any) -> str:
    return re.sub(r"[\s_-]+", " ", str(value or "").strip().casefold())


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


def _numeric_field(value: Any, expected: float | None) -> bool:
    parsed = _number(value)
    if expected is None:
        return parsed is None
    return parsed is not None and math.isclose(parsed, expected, abs_tol=1e-6)


def _page_id(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    match = re.fullmatch(r"(?:page\s*)?(\d+)(?:\.json)?", _norm(value))
    return int(match.group(1)) if match else None


def _add(
    checks: list[dict[str, Any]],
    check_id: str,
    passed: bool,
    detail: Any = None,
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
        with (root / "indicator_panel.csv").open(
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

    by_key = {(row["country"], row["year"]): row for row in rows}
    integrity = (
        header == HEADER
        and len(rows) == len(EXPECTED)
        and len(by_key) == len(EXPECTED)
        and set(by_key) == set(EXPECTED)
    )
    _add(
        checks,
        "ledger_integrity",
        integrity,
        {"header": header, "keys": sorted(f"{a}/{b}" for a, b in by_key)},
    )

    for index, (key, expected) in enumerate(EXPECTED.items(), start=1):
        row = by_key.get(key, {})
        detail = {
            "indicator": _norm(row.get("indicator")) == _norm(expected[0]),
            "unit": _norm(row.get("unit")) == _norm(expected[1]),
            "value": _numeric_field(row.get("value"), expected[2]),
            "revision": _numeric_field(row.get("revision_from_prior"), expected[3]),
        }
        _add(
            checks,
            f"ledger_item_{index}",
            integrity and all(detail.values()),
            detail,
        )

    state: dict[str, Any] = {}
    try:
        candidate = json.loads(
            (root / "vintage_state.json").read_text(encoding="utf-8")
        )
        if isinstance(candidate, dict):
            state = candidate
    except Exception:
        state = {}
    pages = state.get("pages_consumed")
    page_ids = [_page_id(value) for value in pages] if isinstance(pages, list) else []
    state_detail = {
        "indicator": _norm(state.get("indicator")) == "gdpcon15",
        "unit": _norm(state.get("unit")) == "constant 2015 credits",
        "vintage": str(state.get("vintage") or "").strip() == "2026-07",
        "pages": len(page_ids) == 3 and set(page_ids) == {1, 2, 3},
        "row_count": state.get("row_count") == 9,
        "leader": _norm(state.get("2025_leader")) == "cygnus",
    }
    _add(checks, "aggregate_state", all(state_detail.values()), state_detail)

    note_path = root / "revision_note.md"
    note = (
        note_path.read_text(encoding="utf-8", errors="replace")
        if note_path.is_file()
        else ""
    )
    normalized = _norm(note)
    _add(
        checks,
        "report_indicator",
        "gdpcon15" in normalized and "constant 2015" in normalized,
    )
    _add(
        checks,
        "report_pages",
        (
            any(term in normalized for term in ("page 1", "page1"))
            and any(term in normalized for term in ("page 2", "page2"))
            and any(term in normalized for term in ("page 3", "page3"))
        )
        or bool(
            re.search(
                r"pages?\s+1\s*,\s*2\s*,?\s*(?:and|&)\s*3\b",
                normalized,
            )
        )
        or bool(re.search(r"pages?\s+1\s*(?:-|through|to)\s*3\b", normalized)),
    )
    _add(
        checks,
        "report_revisions",
        "revision" in normalized
        and "aster" in normalized
        and "boron" in normalized
        and "cygnus" in normalized
        and all(token in note for token in ("+2", "+5", "-5", "-2", "+3")),
    )
    _add(
        checks,
        "report_leader_safety",
        "cygnus" in normalized
        and "2025" in normalized
        and not any(
            term in normalized
            for term in ("global leader", "world leader", "all countries")
        )
        and (
            any(
                term in normalized
                for term in (
                    "limit",
                    "requested countries",
                    "three countries",
                    "local",
                )
            )
            or (
                any(
                    term in normalized
                    for term in (
                        "ahead of boron",
                        "compared with boron",
                        "versus boron",
                    )
                )
            )
        ),
    )

    derived_leader = None
    if integrity:
        rows_2025 = [row for (country, year), row in by_key.items() if year == "2025"]
        if len(rows_2025) == 3 and all(
            _number(row.get("value")) is not None for row in rows_2025
        ):
            derived_leader = max(
                rows_2025, key=lambda row: _number(row.get("value")) or float("-inf")
            )["country"]
    indicators = {_norm(row.get("indicator")) for row in rows}
    units = {_norm(row.get("unit")) for row in rows}
    closure = (
        integrity
        and state.get("row_count") == len(rows)
        and len(indicators) == 1
        and _norm(state.get("indicator")) in indicators
        and len(units) == 1
        and _norm(state.get("unit")) in units
        and _norm(state.get("2025_leader")) == _norm(derived_leader)
    )
    _add(
        checks,
        "cross_artifact_closure",
        closure,
        {"derived_leader": derived_leader, "row_count": len(rows)},
    )

    return {
        "task": "084-indicator-vintage-reconcile",
        "workspace": str(root),
        "outcome_score": sum(bool(check["pass"]) for check in checks) / len(checks),
        "checks": checks,
    }
