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

def kernel_244(events: list[dict[str, Any]]) -> dict[str, Any]:
    # CG = sum(w*arm)/sum(w); envelope 18-32; max 18000
    seen: set[str] = set()
    weight = 12000.0
    moment = 12000.0 * 24.0
    decisions = []
    for index, event in enumerate(events):
        item_id = str(event.get("load_id") or "")
        try:
            w = float(event.get("weight_lb") or "")
            arm = float(event.get("arm_in") or "")
        except ValueError:
            w, arm = -1.0, 0.0
        if (not item_id) or item_id in seen or w < 0:
            decision = "malformed"
        else:
            next_w = weight + w
            next_m = moment + w * arm
            cg = next_m / next_w if next_w else 0.0
            if next_w > 18000 or cg < 18 or cg > 32:
                decision = "conflict"
            else:
                decision = "recorded"
                weight, moment = next_w, next_m
        if item_id:
            seen.add(item_id)
        decisions.append({"index": index, "item_id": item_id, "decision": decision})
    return _pack(decisions)


plan = kernel_244
