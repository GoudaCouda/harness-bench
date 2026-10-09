"""Trusted recomputation of the Harborwatch SSO audit quarantine.

This module is grader-only. It never imports the agent-visible controller and
never reads candidate-authored artifacts as evidence.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

DECISIONS = ("accepted", "quarantined", "malformed")
TOKEN_FIELDS = {"access_token", "refresh_token", "password", "secret", "authorization"}


def _counts(decisions: list[dict[str, Any]]) -> dict[str, int]:
    tallies = {name: 0 for name in DECISIONS}
    tallies.update(Counter(str(row["decision"]) for row in decisions))
    return tallies


def _contains_secret(event: dict[str, Any]) -> bool:
    for key, value in event.items():
        if str(key).casefold() in TOKEN_FIELDS and str(value).strip():
            return True
    return False


def _redact(event: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(event)
    for key, value in list(redacted.items()):
        if str(key).casefold() in TOKEN_FIELDS and str(value).strip():
            redacted[key] = "[REDACTED]"
    return redacted


def plan(events: list[dict[str, Any]]) -> dict[str, Any]:
    seen_ids: set[str] = set()
    decisions: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        event_id = str(event.get("event_id") or "")
        correlation_id = str(event.get("correlation_id") or "")
        if not event_id or event_id in seen_ids or not correlation_id:
            decision = "malformed"
        elif _contains_secret(event):
            decision = "quarantined"
        else:
            decision = "accepted"
        if event_id:
            seen_ids.add(event_id)
        redacted = _redact(event)
        decisions.append(
            {
                "index": index,
                "event_id": event_id,
                "correlation_id": correlation_id,
                "decision": decision,
            }
        )
        records.append(
            {
                "index": index,
                "event_id": event_id,
                "correlation_id": correlation_id,
                "decision": decision,
                "record": redacted,
            }
        )
    accepted = [row["event_id"] for row in decisions if row["decision"] == "accepted"]
    quarantined = [row["event_id"] for row in decisions if row["decision"] == "quarantined"]
    return {
        "decisions": decisions,
        "records": records,
        "counts": _counts(decisions),
        "accepted_ids": accepted,
        "quarantined_ids": quarantined,
    }
