"""Trusted recomputation of Release I-9 cases only with unexpired List A or B+C evidence.

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

def plan_225(events: list[dict[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    decisions: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        item_id = str(event.get("case_id") or "")
        expired = bool(event.get("expired"))
        list_a = bool(event.get("list_a"))
        list_b = bool(event.get("list_b"))
        list_c = bool(event.get("list_c"))
        if _malformed(event, seen, "case_id", "employee_id"):
            decision = "malformed"
        elif expired:
            decision = "suppressed"
        elif list_a or (list_b and list_c):
            decision = "released"
        else:
            decision = "suppressed"
        if item_id:
            seen.add(item_id)
        decisions.append(
            {
                "index": index,
                "item_id": item_id,
                "employee_id": str(event.get("employee_id") or ""),
                "decision": decision,
            }
        )
    return _pack(decisions, ("released", "suppressed", "malformed"), "released", "suppressed")


plan = plan_225
