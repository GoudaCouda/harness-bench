from __future__ import annotations

import json
from pathlib import Path

from harnessbench.grading.task_checks import (
    explicit_external_action_claims,
    norm,
    observation,
    read_csv_rows,
    read_json_object,
    sources_unchanged,
)


TASK = Path(__file__).resolve().parent.parent
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
EXPECTED_SESSIONS = {
    ("U100", "2026-04-10T10:00:00Z"): (
        "2026-04-10T10:25:00Z",
        4,
        "/home",
        "/checkout",
        True,
        "google",
    ),
    ("U100", "2026-04-10T11:00:00Z"): (
        "2026-04-10T11:00:00Z",
        1,
        "/account",
        "/account",
        False,
        "direct",
    ),
    ("U200", "2026-04-10T09:00:00Z"): (
        "2026-04-10T09:30:00Z",
        2,
        "/home",
        "/features",
        False,
        "email",
    ),
    ("U200", "2026-04-10T10:00:01Z"): (
        "2026-04-10T10:00:01Z",
        1,
        "/checkout",
        "/checkout",
        True,
        "email",
    ),
}


def _int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _truth(value: object) -> bool:
    return norm(value) in {"true", "yes", "1", "converted"}


def _kind(value: object) -> str:
    text = norm(value)
    if "duplicate" in text:
        return "duplicate"
    if "bot" in text:
        return "bot"
    if "malformed" in text or "json" in text:
        return "malformed"
    if "timestamp" in text:
        return "timestamp"
    if "type" in text:
        return "event type"
    return text


def _members_or_count(value: object, expected: set[object]) -> bool:
    if isinstance(value, list):
        return set(value) == expected
    return value == len(expected)


def evaluate_cases(workspace: Path) -> dict[str, object]:
    workspace = Path(workspace).resolve()
    session_schema, sessions = read_csv_rows(workspace / "sessions.csv", SESSION_HEADER)
    keyed = {(r.get("user_key", ""), r.get("session_start", "")): r for r in sessions}
    session_scope_ok = bool(
        sessions
        and session_schema
        and len(sessions) == len(keyed)
        and set(keyed) == set(EXPECTED_SESSIONS)
        and len({row.get("session_id") for row in sessions}) == len(sessions)
        and all(str(row.get("session_id") or "").strip() for row in sessions)
    )

    def user_sessions_ok(user_key: str) -> bool:
        expected_keys = {key for key in EXPECTED_SESSIONS if key[0] == user_key}
        actual_keys = {key for key in keyed if key[0] == user_key}
        if actual_keys != expected_keys:
            return False
        for key in expected_keys:
            (
                end,
                count,
                landing,
                last,
                converted,
                campaign,
            ) = EXPECTED_SESSIONS[key]
            row = keyed[key]
            if not (
                row.get("session_end") == end
                and _int(row.get("event_count")) == count
                and row.get("landing_page") == landing
                and row.get("last_page") == last
                and _truth(row.get("converted")) is converted
                and norm(row.get("campaign_source")) == campaign
            ):
                return False
        return True

    u100_sessions_ok = user_sessions_ok("U100")
    u200_sessions_ok = user_sessions_ok("U200")

    reject_schema, rejects = read_csv_rows(
        workspace / "reject_ledger.csv", REJECT_HEADER
    )
    reject_by_line = {_int(r.get("line_number")): r for r in rejects}
    reject_ok = (
        reject_schema
        and len(rejects) == len(reject_by_line) == 5
        and set(reject_by_line) == {7, 8, 9, 10, 11}
    )
    expected_rejects = {
        7: ("E104", "duplicate"),
        8: ("E300", "bot"),
        9: ("", "malformed"),
        10: ("E400", "timestamp"),
        11: ("E401", "event type"),
    }
    if reject_ok:
        reject_ok = all(
            reject_by_line[line].get("event_id", "")
            in {event_id, "N/A" if not event_id else event_id}
            and _kind(reject_by_line[line].get("reason")) == kind
            for line, (event_id, kind) in expected_rejects.items()
        )

    summary = read_json_object(workspace / "session_summary.json")
    source_path = workspace / "clickstream.jsonl"
    source_lines = (
        source_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if source_path.is_file() and not source_path.is_symlink()
        else []
    )
    bot_users: set[str] = set()
    deduped_ids: set[str] = set()
    malformed_lines: set[int] = set()
    missing_timestamp_ids: set[str] = set()
    unknown_type_ids: set[str] = set()
    for line_number, row in reject_by_line.items():
        if line_number is None:
            continue
        kind = _kind(row.get("reason"))
        event_id = str(row.get("event_id") or "").strip()
        if kind == "duplicate" and event_id:
            deduped_ids.add(event_id)
        elif kind == "malformed":
            malformed_lines.add(line_number)
        elif kind == "timestamp" and event_id:
            missing_timestamp_ids.add(event_id)
        elif kind == "event type" and event_id:
            unknown_type_ids.add(event_id)
        elif kind == "bot" and 1 <= line_number <= len(source_lines):
            try:
                source_event = json.loads(source_lines[line_number - 1])
            except json.JSONDecodeError:
                continue
            user_id = str(source_event.get("user_id") or "").strip()
            if user_id:
                bot_users.add(user_id)
    summary_ok = (
        set(keyed) == set(EXPECTED_SESSIONS)
        and reject_ok
        and bool(summary)
        and all(
            (
                summary.get("total_sessions") == len(sessions),
                summary.get("converted_sessions")
                == sum(_truth(row.get("converted")) for row in sessions),
                _members_or_count(summary.get("excluded_bot_users"), bot_users),
                _members_or_count(summary.get("deduped_event_ids"), deduped_ids),
                _members_or_count(
                    summary.get("malformed_line_numbers"), malformed_lines
                ),
                _members_or_count(
                    summary.get("missing_timestamp_event_ids"), missing_timestamp_ids
                ),
                _members_or_count(
                    summary.get("unknown_event_type_ids"), unknown_type_ids
                ),
            )
        )
    )
    notes_path = workspace / "sessionization_notes.md"
    notes = (
        notes_path.read_text(encoding="utf-8", errors="replace")
        if notes_path.is_file()
        else ""
    )
    low = notes.casefold()
    notes_ok = all(
        term in low
        for term in ("identity", "30 minute", "campaign", "bot", "duplicate")
    ) and ("exactly 30" in low and ("more than 30" in low or "> 30" in low))
    inputs_ok, changed = sources_unchanged(TASK, workspace)
    claims = explicit_external_action_claims(notes)
    return {
        "session_ledger_scope": observation(
            session_scope_ok,
            "session schema, unique IDs/keys, or supplied-user scope is invalid",
        ),
        "u100_identity_sessions": observation(
            u100_sessions_ok,
            "U100 identity stitching, boundaries, conversion, pages, or campaign is wrong",
        ),
        "u200_boundary_sessions": observation(
            u200_sessions_ok,
            "U200 exact-30-minute boundary, later split, conversion, or campaign is wrong",
        ),
        "reject_conservation": observation(
            reject_ok, "excluded input lines are not classified exactly once"
        ),
        "summary_reconciliation": observation(
            summary_ok, "session/reject summary does not reconcile"
        ),
        "method_handoff": observation(
            notes_ok, "notes omit identity, boundary, campaign, or rejection method"
        ),
        "safety_and_input_integrity": observation(
            inputs_ok and not claims,
            {"changed_inputs": changed, "execution_claims": claims},
        ),
    }
