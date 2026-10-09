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

def kernel_247(events: list[dict[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    legal = {"A", "B", "C"}
    decisions = []
    for index, event in enumerate(events):
        item_id = str(event.get("ballot_id") or "")
        ranking = event.get("ranking")
        if (not item_id) or item_id in seen or not isinstance(ranking, list) or not ranking:
            decision = "malformed"
        else:
            names = [str(x) for x in ranking]
            if len(names) != len(set(names)) or any(name not in legal for name in names):
                decision = "conflict"
            else:
                decision = "recorded"
        if item_id:
            seen.add(item_id)
        decisions.append({"index": index, "item_id": item_id, "decision": decision})
    return _pack(decisions)


plan = kernel_247
