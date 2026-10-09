"""Trusted recomputation. Grader-only; never imported by the controller."""

from __future__ import annotations

from collections import Counter
from typing import Any

def _counts(decisions: list[dict[str, Any]]) -> dict[str, int]:
    tallies = {"recorded": 0, "conflict": 0, "malformed": 0}
    tallies.update(Counter(row["decision"] for row in decisions))
    return tallies

def _pack(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "decisions": decisions,
        "counts": _counts(decisions),
        "recorded_ids": [row["item_id"] for row in decisions if row["decision"] == "recorded"],
        "conflict_ids": [row["item_id"] for row in decisions if row["decision"] == "conflict"],
    }

def kernel_238(events: list[dict[str, Any]]) -> dict[str, Any]:
    static = {"T1", "T2", "T4"}
    seen: set[str] = set()
    cancelled: set[str] = set()
    decisions = []
    for index, event in enumerate(events):
        item_id = str(event.get("event_id") or "")
        trip_id = str(event.get("trip_id") or "")
        event_type = str(event.get("event_type") or "")
        if (not item_id) or item_id in seen or (not trip_id):
            decision = "malformed"
        elif trip_id not in static or trip_id in cancelled:
            decision = "conflict"
        elif event_type == "cancelled":
            cancelled.add(trip_id)
            decision = "conflict"
        else:
            decision = "recorded"
        if item_id:
            seen.add(item_id)
        decisions.append({"index": index, "item_id": item_id, "trip_id": trip_id, "decision": decision})
    return _pack(decisions)


plan = kernel_238
