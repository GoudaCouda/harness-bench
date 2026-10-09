"""Trusted recomputation of Record flaky tests only after three real failures, ignoring infra errors.

This module is grader-only. It never imports the agent-visible controller and
never reads candidate-authored artifacts as evidence.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

def _counts(decisions: list[dict[str, Any]], vocab: tuple[str, ...]) -> dict[str, int]:
    tallies = {name: 0 for name in vocab}
    tallies.update(Counter(str(row["decision"]) for row in decisions))
    return tallies

def _pack(
    decisions: list[dict[str, Any]],
    vocab: tuple[str, ...],
    primary: str,
    secondary: str,
) -> dict[str, Any]:
    return {
        "decisions": decisions,
        "counts": _counts(decisions, vocab),
        f"{primary}_ids": [row["item_id"] for row in decisions if row["decision"] == primary],
        f"{secondary}_ids": [row["item_id"] for row in decisions if row["decision"] == secondary],
    }

def _malformed(event: dict[str, Any], seen: set[str], id_key: str, extra_required: str) -> bool:
    item_id = str(event.get(id_key) or "")
    extra = str(event.get(extra_required) or "")
    return (not item_id) or item_id in seen or (not extra)

def plan_234(events: list[dict[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    decisions: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        item_id = str(event.get("test_id") or "")
        fails = int(event.get("fails") or 0)
        runs = int(event.get("runs") or 0)
        infra = int(event.get("infra_errors") or 0)
        if _malformed(event, seen, "test_id", "suite") or runs <= 0:
            decision = "malformed"
        elif fails >= 3:
            decision = "recorded"
        elif infra > 0 and fails == 0:
            decision = "conflict"
        else:
            decision = "conflict"
        if item_id:
            seen.add(item_id)
        decisions.append(
            {
                "index": index,
                "item_id": item_id,
                "suite": str(event.get("suite") or ""),
                "decision": decision,
            }
        )
    return _pack(decisions, ("recorded", "conflict", "malformed"), "recorded", "conflict")


plan = plan_234
