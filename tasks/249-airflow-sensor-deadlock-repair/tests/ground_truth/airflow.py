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

def kernel_249(events: list[dict[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    waits: dict[str, str] = {}
    decisions = []

    def cycle(src: str, dst: str) -> bool:
        cursor = dst
        guard = 0
        while cursor in waits and guard < 16:
            if waits[cursor] == src:
                return True
            cursor = waits[cursor]
            guard += 1
        return False

    for index, event in enumerate(events):
        item_id = str(event.get("task_id") or "")
        waits_for = str(event.get("waits_for") or "")
        if (not item_id) or item_id in seen or (not waits_for):
            decision = "malformed"
        elif waits_for == item_id or cycle(item_id, waits_for):
            decision = "conflict"
        else:
            decision = "recorded"
            waits[item_id] = waits_for
        if item_id:
            seen.add(item_id)
        decisions.append({"index": index, "item_id": item_id, "waits_for": waits_for, "decision": decision})
    return _pack(decisions)


plan = kernel_249
