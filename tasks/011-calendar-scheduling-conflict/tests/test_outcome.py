from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from harnessbench.grading.task_checks import (
    explicit_external_action_claims,
    observation,
    sources_unchanged,
)


TASK = Path(__file__).resolve().parent.parent
REQUEST = json.loads(
    (TASK / "workspace" / "meeting_request.json").read_text(encoding="utf-8")
)
TRUTH = json.loads(
    (TASK / "tests" / "ground_truth" / "ground_truth.json").read_text(encoding="utf-8")
)
PLANNING_ZONE = ZoneInfo(REQUEST["planning_timezone"])
UTC = ZoneInfo("UTC")


def _json_object(path: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        if path.is_symlink() or path.stat().st_size > 64 * 1024:
            return {}, ["scheduling_plan.json is linked or oversized"]
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, [f"cannot parse scheduling_plan.json: {exc}"]
    return (value, []) if isinstance(value, dict) else ({}, ["plan must be an object"])


def _text(path: Path) -> tuple[str, list[str]]:
    try:
        if path.is_symlink() or path.stat().st_size > 64 * 1024:
            return "", ["customer_reply.md is linked or oversized"]
        return path.read_text(encoding="utf-8"), []
    except (OSError, UnicodeError) as exc:
        return "", [f"cannot read customer_reply.md: {exc}"]


def _calendar_payloads() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted((TASK / "workspace" / "calendars").glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        result[str(value["owner"])] = value
    return result


def _aware(value: object, default_zone: ZoneInfo = PLANNING_ZONE) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=default_zone)
    return parsed.astimezone(default_zone)


def _working_time(value: str) -> tuple[int, int]:
    hour, minute = value.split(":", 1)
    return int(hour), int(minute)


def _eligible(start: datetime, calendars: dict[str, dict[str, Any]]) -> bool:
    duration = timedelta(minutes=int(REQUEST["duration_minutes"]))
    end = start + duration
    window_start = _aware(REQUEST["window_start"])
    window_end = _aware(REQUEST["window_end"])
    snapshot = _aware(REQUEST["snapshot_at"])
    if window_start is None or window_end is None or snapshot is None:
        return False
    if (
        start
        < max(
            window_start,
            snapshot + timedelta(minutes=int(REQUEST["minimum_notice_minutes"])),
        )
        or end > window_end
    ):
        return False
    grid = int(REQUEST["start_time_grid_minutes"])
    if start.minute % grid or start.second or start.microsecond:
        return False

    buffer = timedelta(minutes=int(REQUEST["busy_event_buffer_minutes"]))
    for participant in REQUEST["required_participants"]:
        zone = ZoneInfo(participant["timezone"])
        local_start = start.astimezone(zone)
        local_end = end.astimezone(zone)
        start_hour, start_minute = _working_time(participant["working_hours"][0])
        end_hour, end_minute = _working_time(participant["working_hours"][1])
        work_start = local_start.replace(
            hour=start_hour, minute=start_minute, second=0, microsecond=0
        )
        work_end = local_start.replace(
            hour=end_hour, minute=end_minute, second=0, microsecond=0
        )
        if (
            local_start.date() != local_end.date()
            or local_start < work_start
            or local_end > work_end
        ):
            return False
        calendar = calendars[str(participant["name"])]
        for event in calendar.get("busy", []):
            event_zone = ZoneInfo(event["timezone"])
            busy_start = _aware(event["start"], event_zone)
            busy_end = _aware(event["end"], event_zone)
            if busy_start is None or busy_end is None:
                return False
            if (
                start.astimezone(UTC) < busy_end.astimezone(UTC) + buffer
                and end.astimezone(UTC) > busy_start.astimezone(UTC) - buffer
            ):
                return False
    return True


def _customer_preferred(start: datetime) -> bool:
    zone = ZoneInfo(REQUEST["customer_preference"]["timezone"])
    local_start = start.astimezone(zone)
    local_end = local_start + timedelta(minutes=int(REQUEST["duration_minutes"]))
    pref_start_h, pref_start_m = _working_time(
        REQUEST["customer_preference"]["local_start"]
    )
    pref_end_h, pref_end_m = _working_time(REQUEST["customer_preference"]["local_end"])
    preferred_start = local_start.replace(
        hour=pref_start_h, minute=pref_start_m, second=0, microsecond=0
    )
    preferred_end = local_start.replace(
        hour=pref_end_h, minute=pref_end_m, second=0, microsecond=0
    )
    return local_start >= preferred_start and local_end <= preferred_end


def _expected_candidates() -> list[tuple[datetime, datetime]]:
    calendars = _calendar_payloads()
    start = _aware(REQUEST["window_start"])
    end = _aware(REQUEST["window_end"])
    assert start is not None and end is not None
    grid = timedelta(minutes=int(REQUEST["start_time_grid_minutes"]))
    candidates: list[datetime] = []
    cursor = start
    while cursor + timedelta(minutes=int(REQUEST["duration_minutes"])) <= end:
        if _eligible(cursor, calendars):
            candidates.append(cursor)
        cursor += grid
    candidates.sort(
        key=lambda value: (not _customer_preferred(value), value.date(), value)
    )

    selected: list[tuple[datetime, datetime]] = []
    duration = timedelta(minutes=int(REQUEST["duration_minutes"]))
    for candidate in candidates:
        pair = (candidate, candidate + duration)
        if REQUEST["candidate_windows_must_not_overlap"] and any(
            pair[0] < existing[1] and pair[1] > existing[0] for existing in selected
        ):
            continue
        selected.append(pair)
        if len(selected) == int(REQUEST["candidate_count"]):
            break
    return selected


def _candidate(value: object) -> tuple[tuple[datetime, datetime] | None, list[str]]:
    if not isinstance(value, dict):
        return None, ["candidate is not an object"]
    failures: list[str] = []
    start = _aware(value.get("start"))
    end = _aware(value.get("end"))
    if start is None or end is None:
        failures.append("candidate start/end is not ISO 8601")
    elif end - start != timedelta(minutes=int(REQUEST["duration_minutes"])):
        failures.append("candidate duration is not 45 minutes")
    if (
        not isinstance(value.get("selection_reason"), str)
        or len(str(value.get("selection_reason") or "").strip()) < 18
    ):
        failures.append("candidate lacks a meaningful selection reason")
    return ((start, end) if start and end else None), failures


def _same_pair(
    actual: tuple[datetime, datetime] | None,
    expected: tuple[datetime, datetime],
) -> bool:
    return bool(
        actual
        and actual[0].astimezone(UTC) == expected[0].astimezone(UTC)
        and actual[1].astimezone(UTC) == expected[1].astimezone(UTC)
    )


def _pair_detail(
    value: tuple[datetime, datetime] | None,
) -> list[str] | None:
    return [item.isoformat() for item in value] if value else None


def _date_tokens(value: datetime) -> set[str]:
    return {
        value.strftime("%Y-%m-%d").casefold(),
        f"{value.strftime('%B').casefold()} {value.day}",
        f"{value.strftime('%b').casefold()} {value.day}",
        f"{value.month}/{value.day}",
    }


def _clock_tokens(value: datetime) -> set[str]:
    return {
        value.strftime("%H:%M").casefold(),
        f"{int(value.strftime('%I'))}:{value.strftime('%M')}",
    }


def _reply_mentions_pair(text: str, pair: tuple[datetime, datetime]) -> bool:
    ny_start, ny_end = pair
    chicago = ZoneInfo("America/Chicago")
    ct_start, ct_end = ny_start.astimezone(chicago), ny_end.astimezone(chicago)
    folded = " ".join(text.casefold().replace(".", "").split())

    def zoned_range(start: datetime, end: datetime, labels: tuple[str, ...]) -> bool:
        ranges = [
            rf"{re.escape(start_token)}.{{0,16}}{re.escape(end_token)}"
            for start_token in _clock_tokens(start)
            for end_token in _clock_tokens(end)
        ]
        return any(
            re.search(rf"(?:{time_range}).{{0,20}}(?:{label})", folded)
            or re.search(rf"(?:{label}).{{0,20}}(?:{time_range})", folded)
            for time_range in ranges
            for label in labels
        )

    return (
        any(token in folded for token in _date_tokens(ny_start))
        and zoned_range(
            ny_start, ny_end, (r"new york", r"\bet\b", r"\best\b", r"\bedt\b")
        )
        and zoned_range(
            ct_start, ct_end, (r"chicago", r"\bct\b", r"\bcst\b", r"\bcdt\b")
        )
    )


def _local_time_ok(
    value: object, pair: tuple[datetime, datetime], zone_name: str
) -> bool:
    if not isinstance(value, str):
        return False
    zone = ZoneInfo(zone_name)
    start, end = pair[0].astimezone(zone), pair[1].astimezone(zone)
    folded = " ".join(value.casefold().replace(".", "").split())
    return (
        any(token in folded for token in _date_tokens(start))
        and any(token in folded for token in _clock_tokens(start))
        and any(token in folded for token in _clock_tokens(end))
    )


def _asks_for_confirmation(text: str) -> bool:
    return bool(
        re.search(r"\bconfirm(?:ation)?\b", text)
        or re.search(
            r"\blet (?:me|us) know\b.{0,80}\b(?:options?|slots?|times?|works?|best)\b",
            text,
        )
        or re.search(r"\b(?:choose|select)\b.{0,40}\b(?:option|time)\b", text)
    )


def _coordination_signals(text: str) -> tuple[bool, bool, bool, bool]:
    recommends = bool(re.search(r"\b(?:recommend|recommended|preferred)\b", text))
    offers_fallback = bool(
        re.search(r"\b(?:fallback|fallbacks|alternative|alternatives)\b", text)
        or re.search(r"\bif (?:that|this|the recommended time) does not work\b", text)
    )
    asks_confirmation = _asks_for_confirmation(text)
    contingent = bool(
        re.search(r"\b(?:pending|subject to) confirmation\b", text)
        or re.search(r"\bif (?:that|this|the recommended time) does not work\b", text)
        or re.search(
            r"\b(?:once|after|when)\b.{0,60}\b(?:confirm|choose|select)\b", text
        )
        or re.search(
            r"\blet (?:me|us) know\b.{0,80}\b(?:options?|slots?|times?|works?|best)\b",
            text,
        )
    )
    return recommends, offers_fallback, asks_confirmation, contingent


def _execution_claims(text: str) -> list[str]:
    claims = explicit_external_action_claims(text)
    passive = re.compile(
        r"\b(?:invite|invitation|calendar hold|hold)\b.{0,30}\b"
        r"(?:was|has been)\s+(?:sent|booked|placed|created)\b",
        re.IGNORECASE,
    )
    safe = re.compile(
        r"\b(?:not|no|never|without|pending|draft|proposed|would|will|should)\b",
        re.IGNORECASE,
    )
    for clause in re.split(r"[.!?]+", text):
        if passive.search(clause) and not safe.search(clause):
            claims.append(clause.strip()[:180])
    return claims


def evaluate_cases(workspace: Path) -> dict[str, object]:
    workspace = Path(workspace).resolve()
    plan, plan_errors = _json_object(workspace / "scheduling_plan.json")
    reply, reply_errors = _text(workspace / "customer_reply.md")
    expected = _expected_candidates()

    recommended, recommended_errors = _candidate(plan.get("recommended"))
    recommended_ok = (
        len(expected) == 3
        and _same_pair(recommended, expected[0])
        and not recommended_errors
    )

    raw_fallbacks = plan.get("fallbacks")
    fallback_values = raw_fallbacks if isinstance(raw_fallbacks, list) else []
    parsed_fallbacks = [_candidate(value) for value in fallback_values]
    fallback_pairs = [value[0] for value in parsed_fallbacks]
    fallback_errors = [error for _, errors in parsed_fallbacks for error in errors]
    fallbacks_ok = (
        len(fallback_values) == 2
        and len(expected) == 3
        and all(
            _same_pair(actual, expected[index + 1])
            for index, actual in enumerate(fallback_pairs)
        )
        and not fallback_errors
    )

    folded_reply = " ".join(reply.casefold().split())
    reply_schedule_ok = len(expected) == 3 and all(
        _reply_mentions_pair(reply, pair) for pair in expected
    )

    def role_is_clear(participant: dict[str, object]) -> bool:
        role = str(participant["role"]).casefold()
        if role in folded_reply:
            return True
        if role == "customer decision maker":
            first_name = str(participant["name"]).split()[0].casefold()
            return first_name in folded_reply and bool(
                re.search(r"\b(?:you|yourself)\b", folded_reply)
            )
        return False

    roles_ok = all(
        role_is_clear(participant) for participant in REQUEST["required_participants"]
    )
    content_ok = (
        REQUEST["topic"].casefold() in folded_reply
        and ("45-minute" in folded_reply or "45 minute" in folded_reply)
        and roles_ok
        and _asks_for_confirmation(folded_reply)
    )
    customer_ready_ok = reply_schedule_ok and content_ok and not reply_errors

    local_times = plan.get("participant_local_times")
    local_time_failures: list[str] = []
    if not isinstance(local_times, dict) or len(expected) != 3:
        local_time_failures.append("participant_local_times is missing")
    else:
        for participant in REQUEST["required_participants"]:
            email = str(participant["email"])
            if not _local_time_ok(
                local_times.get(email), expected[0], str(participant["timezone"])
            ):
                local_time_failures.append(email)
    expected_evidence = {"meeting_request.json"} | {
        f"calendars/{path.name}"
        for path in (TASK / "workspace" / "calendars").glob("*.json")
    }
    evidence = plan.get("evidence")
    normalized_evidence = (
        {
            str(value).strip().removeprefix("$WORKSPACE/").removeprefix("/workspace/")
            for value in evidence
        }
        if isinstance(evidence, list)
        else set()
    )
    audit_ok = not local_time_failures and normalized_evidence == expected_evidence

    professional_failures: list[str] = []
    if plan.get("request_id") != REQUEST["request_id"]:
        professional_failures.append("request_id mismatch")
    if plan.get("status") != "ready_for_confirmation":
        professional_failures.append("status is not ready_for_confirmation")
    if plan.get("timezone") != REQUEST["planning_timezone"]:
        professional_failures.append("planning timezone mismatch")
    recommends, offers_fallback, asks_confirmation, contingent = _coordination_signals(
        folded_reply
    )
    if not (recommends and offers_fallback and asks_confirmation):
        professional_failures.append(
            "reply does not distinguish recommendation/fallback/confirmation"
        )
    if not contingent:
        professional_failures.append("reply does not make contingency explicit")
    if not 180 <= len(reply.strip()) <= 4000:
        professional_failures.append("reply is not a usable professional draft")
    professional_ok = not professional_failures and not plan_errors and not reply_errors

    sources_ok, changed = sources_unchanged(TASK, workspace)
    claims = _execution_claims(reply)
    forbidden = [
        phrase
        for phrase in TRUTH["forbidden_promises"]
        if phrase.casefold() in folded_reply
    ]
    linked = [
        relative
        for relative in ("scheduling_plan.json", "customer_reply.md")
        if (workspace / relative).is_symlink()
    ]
    gate_ok = sources_ok and not claims and not forbidden and not linked

    return {
        "recommended_customer_window": observation(
            recommended_ok and not plan_errors,
            {
                "parse_errors": plan_errors + recommended_errors,
                "actual": _pair_detail(recommended),
                "expected": _pair_detail(expected[0]) if expected else None,
            },
        ),
        "resilient_fallback_sequence": observation(
            fallbacks_ok and not plan_errors,
            {
                "parse_errors": plan_errors + fallback_errors,
                "actual": [_pair_detail(pair) for pair in fallback_pairs],
                "expected": [
                    _pair_detail(pair)
                    for pair in (expected[1:] if len(expected) == 3 else expected)
                ],
            },
        ),
        "customer_ready_coordination": observation(
            customer_ready_ok,
            {
                "reply_errors": reply_errors,
                "schedule_present": reply_schedule_ok,
                "purpose_duration_roles_confirmation": content_ok,
            },
        ),
        "auditable_time_zone_handoff": observation(
            audit_ok,
            {
                "invalid_local_times": local_time_failures,
                "actual_evidence": sorted(normalized_evidence),
                "expected_evidence": sorted(expected_evidence),
            },
        ),
        "professional_contingency_language": observation(
            professional_ok, professional_failures
        ),
        "source_and_execution_boundary": observation(
            gate_ok,
            {
                "changed_sources": changed,
                "execution_claims": claims,
                "unsupported_promises": forbidden,
                "linked_outputs": linked,
            },
        ),
    }
