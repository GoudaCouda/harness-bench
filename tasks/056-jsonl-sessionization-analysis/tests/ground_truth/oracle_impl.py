from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parents[2]
FIXTURES = TASK_DIR / "workspace"

SESSION_HEADER = [
    "session_id",
    "user_key",
    "session_start",
    "session_end",
    "event_count",
    "landing_page",
    "last_page",
    "converted",
    "campaign_source",
]
REJECT_HEADER = ["line_number", "event_id", "reason", "notes"]

EXPECTED_SESSIONS = [
    {
        "session_id": "U100-1",
        "user_key": "U100",
        "session_start": "2026-04-10T10:00:00Z",
        "session_end": "2026-04-10T10:25:00Z",
        "event_count": "4",
        "landing_page": "/home",
        "last_page": "/checkout",
        "converted": "true",
        "campaign_source": "google",
    },
    {
        "session_id": "U100-2",
        "user_key": "U100",
        "session_start": "2026-04-10T11:00:00Z",
        "session_end": "2026-04-10T11:00:00Z",
        "event_count": "1",
        "landing_page": "/account",
        "last_page": "/account",
        "converted": "false",
        "campaign_source": "direct",
    },
    {
        "session_id": "U200-1",
        "user_key": "U200",
        "session_start": "2026-04-10T09:00:00Z",
        "session_end": "2026-04-10T09:30:00Z",
        "event_count": "2",
        "landing_page": "/home",
        "last_page": "/features",
        "converted": "false",
        "campaign_source": "email",
    },
    {
        "session_id": "U200-2",
        "user_key": "U200",
        "session_start": "2026-04-10T10:00:01Z",
        "session_end": "2026-04-10T10:00:01Z",
        "event_count": "1",
        "landing_page": "/checkout",
        "last_page": "/checkout",
        "converted": "true",
        "campaign_source": "email",
    },
]
EXPECTED_REJECTS = [
    {
        "line_number": "7",
        "event_id": "E104",
        "reason": "duplicate_event_id",
    },
    {
        "line_number": "8",
        "event_id": "E300",
        "reason": "bot_user",
    },
    {
        "line_number": "9",
        "event_id": "",
        "reason": "malformed_json",
    },
    {
        "line_number": "10",
        "event_id": "E400",
        "reason": "missing_timestamp",
    },
    {
        "line_number": "11",
        "event_id": "E401",
        "reason": "unknown_event_type",
    },
]
EXPECTED_SUMMARY = {
    "total_sessions": 4,
    "converted_sessions": 2,
    "excluded_bot_users": ["U300"],
    "deduped_event_ids": ["E104"],
    "malformed_line_numbers": [9],
    "missing_timestamp_event_ids": ["E400"],
    "unknown_event_type_ids": ["E401"],
}


def _add(
    checks: list[dict[str, Any]],
    check_id: str,
    passed: bool,
    weight: float,
    detail: Any = None,
) -> None:
    checks.append(
        {
            "id": check_id,
            "pass": bool(passed),
            "weight": weight,
            "detail": None if passed else detail,
        }
    )


def _rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        rows = [
            {key: (value or "").strip() for key, value in row.items()} for row in reader
        ]
        return list(reader.fieldnames or []), rows


def _normalized_boolean(value: str) -> str:
    lowered = value.strip().lower()
    if lowered in {"true", "1", "yes"}:
        return "true"
    if lowered in {"false", "0", "no"}:
        return "false"
    return lowered


def _normalized_timestamp(value: str) -> str:
    stripped = value.strip()
    candidate = f"{stripped[:-1]}+00:00" if stripped.lower().endswith("z") else stripped
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return stripped
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return stripped
    return parsed.astimezone(timezone.utc).isoformat()


def _normalized_session(row: dict[str, str]) -> dict[str, str]:
    normalized = {key: str(row.get(key, "")).strip() for key in SESSION_HEADER}
    normalized["converted"] = _normalized_boolean(normalized["converted"])
    for key in ("session_start", "session_end"):
        normalized[key] = _normalized_timestamp(normalized[key])
    return normalized


def _matches_fields(
    actual: dict[str, str] | None,
    expected: dict[str, str],
    fields: tuple[str, ...],
) -> bool:
    return bool(
        actual and all(actual.get(field) == expected.get(field) for field in fields)
    )


def _reason_matches(actual: str, expected: str) -> bool:
    aliases = {
        "bot_user": {"bot_user", "excluded_bot_user", "bot", "excluded_bot"},
        "duplicate_event_id": {"duplicate_event_id", "duplicate"},
        "malformed_json": {"malformed_json", "invalid_json", "parse_error"},
        "missing_timestamp": {"missing_timestamp", "blank_timestamp"},
        "unknown_event_type": {"unknown_event_type", "invalid_event_type"},
    }
    actual_normalized = actual.strip().lower()
    return actual_normalized in aliases.get(expected, {expected})


def _event_id_matches(actual: str, expected: str) -> bool:
    normalized = actual.strip()
    if expected:
        return normalized == expected
    return normalized.lower() in {"", "n/a", "na", "none", "null"}


def _matching_reject(
    rows: list[dict[str, str]],
    expected: dict[str, str],
) -> dict[str, str] | None:
    return next(
        (
            row
            for row in rows
            if row.get("line_number", "") == expected["line_number"]
            and _event_id_matches(
                row.get("event_id", ""),
                expected["event_id"],
            )
            and _reason_matches(
                row.get("reason", ""),
                expected["reason"],
            )
        ),
        None,
    )


def _note_is_informative(note: str, reason: str) -> bool:
    lowered = note.strip().lower()
    if not lowered:
        return False
    if reason == "malformed_json":
        normalized = re.sub(r"[_-]+", " ", lowered)
        explicit_failures = (
            "malformed json",
            "invalid json",
            "bad json",
            "json parse error",
            "json parse problem",
            "json parsing failed",
            "json decode error",
            "json decoder error",
            "json syntax error",
            "could not parse json",
            "cannot parse json",
            "unable to parse json",
            "failed to parse json",
            "parse error",
        )
        if any(phrase in normalized for phrase in explicit_failures):
            return True
        decoder_diagnostic = re.search(
            r"\b(?:"
            r"expecting (?:value|property name enclosed in double quotes|"
            r"['\"]?[,]:['\"]? delimiter)|"
            r"extra data|"
            r"unterminated string starting at|"
            r"invalid (?:\\escape|control character at)"
            r")\s*:?\s*"
            r"line \d+\s+column \d+\s+\(char \d+\)",
            normalized,
        )
        return decoder_diagnostic is not None
    terms = {
        "duplicate_event_id": ("duplicate", "first", "kept"),
        "bot_user": ("bot", "synthetic", "crawler"),
        "missing_timestamp": ("timestamp", "blank", "empty"),
        "unknown_event_type": ("scroll", "event", "type"),
    }
    return any(term in lowered for term in terms[reason])


def _fixture_unchanged(workspace: Path, name: str) -> bool:
    expected = FIXTURES / name
    actual = workspace / name
    return (
        expected.is_file()
        and actual.is_file()
        and expected.read_bytes() == actual.read_bytes()
    )


def _summary_field_matches(
    actual: Any,
    expected: Any,
) -> bool:
    if isinstance(expected, list):
        return isinstance(actual, list) and sorted(map(str, actual)) == sorted(
            map(str, expected)
        )
    return actual == expected


def score_workspace(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    checks: list[dict[str, Any]] = []

    for name in (
        "clickstream.jsonl",
        "session_rules.md",
        "campaign_map.csv",
    ):
        _add(
            checks,
            f"fixture_present_{name}",
            _fixture_unchanged(root, name),
            0.015,
            f"{name} missing or modified",
        )

    sessions_path = root / "sessions.csv"
    _add(
        checks,
        "sessions_exists",
        sessions_path.is_file(),
        0.06,
        "missing sessions.csv",
    )
    session_rows: list[dict[str, str]] = []
    session_header: list[str] = []
    if sessions_path.is_file():
        try:
            session_header, raw_rows = _rows(sessions_path)
            session_rows = [_normalized_session(row) for row in raw_rows]
        except Exception as exc:
            _add(checks, "sessions_parseable", False, 0.0, str(exc))
    _add(
        checks,
        "sessions_header",
        session_header == SESSION_HEADER,
        0.06,
        {"actual": session_header},
    )

    actual_sessions = {
        row.get("session_id", ""): row for row in session_rows if row.get("session_id")
    }
    expected_sessions = {
        row["session_id"]: _normalized_session(row) for row in EXPECTED_SESSIONS
    }
    row_matches: dict[str, bool] = {}
    for session_id, expected in expected_sessions.items():
        passed = actual_sessions.get(session_id) == expected
        row_matches[session_id] = passed
        _add(
            checks,
            f"session_{session_id}",
            passed,
            0.08,
            actual_sessions.get(session_id),
        )
    exact_ids = len(session_rows) == len(EXPECTED_SESSIONS) and set(
        actual_sessions
    ) == set(expected_sessions)
    _add(
        checks,
        "session_set_closed",
        exact_ids,
        0.06,
        sorted(actual_sessions),
    )
    _add(
        checks,
        "sessions_exact",
        exact_ids and all(row_matches.values()),
        0.0,
        {
            "row_matches": row_matches,
            "actual_ids": sorted(actual_sessions),
        },
    )
    identity_fields = (
        "session_id",
        "user_key",
        "session_start",
        "session_end",
        "event_count",
    )
    identity_ok = (
        _matches_fields(
            actual_sessions.get("U100-1"),
            expected_sessions["U100-1"],
            identity_fields,
        )
        and _matches_fields(
            actual_sessions.get("U100-2"),
            expected_sessions["U100-2"],
            identity_fields,
        )
        and not any(row.get("user_key") == "a1" for row in session_rows)
    )
    _add(
        checks,
        "identity_stitching",
        identity_ok,
        0.0,
        {
            "expected_relation": ("all five anonymous_id a1 events stitch to U100"),
            "actual": [
                row for row in session_rows if row.get("user_key") in {"U100", "a1"}
            ],
        },
    )
    boundary_fields = (
        "session_id",
        "user_key",
        "session_start",
        "session_end",
        "event_count",
    )
    u200_rows = [row for row in session_rows if row.get("user_key") == "U200"]
    boundary_ok = (
        len(u200_rows) == 2
        and _matches_fields(
            actual_sessions.get("U200-1"),
            expected_sessions["U200-1"],
            boundary_fields,
        )
        and _matches_fields(
            actual_sessions.get("U200-2"),
            expected_sessions["U200-2"],
            boundary_fields,
        )
    )
    _add(
        checks,
        "thirty_minute_boundary",
        boundary_ok,
        0.0,
        {
            "expected_relation": (
                "09:00 and 09:30 stay together; 10:00:01 starts the next U200 session"
            ),
            "actual": u200_rows,
        },
    )

    rejects_path = root / "reject_ledger.csv"
    _add(
        checks,
        "rejects_exists",
        rejects_path.is_file(),
        0.05,
        "missing reject_ledger.csv",
    )
    reject_rows: list[dict[str, str]] = []
    reject_header: list[str] = []
    if rejects_path.is_file():
        try:
            reject_header, reject_rows = _rows(rejects_path)
        except Exception as exc:
            _add(checks, "rejects_parseable", False, 0.0, str(exc))
    _add(
        checks,
        "rejects_header",
        reject_header == REJECT_HEADER,
        0.05,
        {"actual": reject_header},
    )
    reject_matches: dict[str, bool] = {}
    informative_notes: dict[str, bool] = {}
    for expected in EXPECTED_REJECTS:
        row = _matching_reject(reject_rows, expected)
        key = expected["reason"]
        reject_matches[key] = row is not None
        informative_notes[key] = bool(
            row
            and _note_is_informative(
                row.get("notes", ""),
                expected["reason"],
            )
        )
        _add(
            checks,
            f"reject_{key}",
            row is not None,
            0.02,
            row,
        )
        _add(
            checks,
            f"reject_note_{key}",
            informative_notes[key],
            0.008,
            row,
        )
    rejects_closed = len(reject_rows) == len(EXPECTED_REJECTS) and all(
        reject_matches.values()
    )
    _add(
        checks,
        "reject_set_closed",
        rejects_closed,
        0.02,
        {"rows": len(reject_rows)},
    )
    _add(
        checks,
        "rejects_identity",
        rejects_closed,
        0.0,
        reject_matches,
    )
    _add(
        checks,
        "reject_notes",
        sum(informative_notes.values()) >= len(EXPECTED_REJECTS) - 1,
        0.0,
        informative_notes,
    )

    summary_path = root / "session_summary.json"
    _add(
        checks,
        "summary_exists",
        summary_path.is_file(),
        0.05,
        "missing session_summary.json",
    )
    summary: dict[str, Any] = {}
    if summary_path.is_file():
        try:
            parsed = json.loads(summary_path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                summary = parsed
        except Exception as exc:
            _add(checks, "summary_parseable", False, 0.0, str(exc))
    summary_matches: dict[str, bool] = {}
    summary_weight = 0.12 / len(EXPECTED_SUMMARY)
    for key, expected in EXPECTED_SUMMARY.items():
        passed = _summary_field_matches(summary.get(key), expected)
        summary_matches[key] = passed
        _add(
            checks,
            f"summary_{key}",
            passed,
            summary_weight,
            summary.get(key),
        )
    _add(
        checks,
        "summary_exact",
        all(summary_matches.values()) and set(summary) == set(EXPECTED_SUMMARY),
        0.0,
        summary_matches,
    )

    notes_path = root / "sessionization_notes.md"
    _add(
        checks,
        "notes_exists",
        notes_path.is_file(),
        0.03,
        "missing sessionization_notes.md",
    )
    notes_text = (
        notes_path.read_text(encoding="utf-8", errors="replace").lower()
        if notes_path.is_file()
        else ""
    )
    notes_ok = (
        "identity" in notes_text
        and bool(re.search(r"\b30(?:-|\s+)minute", notes_text))
        and "malformed" in notes_text
        and "duplicate" in notes_text
    )
    _add(
        checks,
        "notes_required",
        notes_ok,
        0.06,
        "must cover identity, 30-minute boundary, malformed, and duplicate",
    )

    total_weight = sum(float(check["weight"]) for check in checks)
    earned = sum(float(check["weight"]) for check in checks if check["pass"])
    score = round(earned / total_weight, 4) if total_weight else 0.0
    fixtures_ok = all(
        check["pass"]
        for check in checks
        if str(check["id"]).startswith("fixture_present_")
    )
    if not fixtures_ok:
        score = 0.0
    return {
        "task": "056-jsonl-sessionization-analysis",
        "workspace": str(root),
        "checks": checks,
        "outcome_score": score,
        "score": score,
    }
