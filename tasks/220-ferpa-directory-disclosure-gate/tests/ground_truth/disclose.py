"""Trusted recomputation of Gate FERPA directory disclosures against opt-out and academic fields.

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

def plan_220(events: list[dict[str, Any]]) -> dict[str, Any]:
    directory = {"name", "email", "major"}
    academic = {"gpa", "grades", "disciplinary"}
    seen: set[str] = set()
    decisions: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        item_id = str(event.get("request_id") or "")
        if _malformed(event, seen, "request_id", "student_id"):
            decision = "malformed"
        elif str(event.get("field") or "") in academic:
            decision = "suppressed"
        elif bool(event.get("opt_out")):
            decision = "suppressed"
        elif str(event.get("field") or "") in directory:
            decision = "released"
        else:
            decision = "suppressed"
        if item_id:
            seen.add(item_id)
        decisions.append(
            {
                "index": index,
                "item_id": item_id,
                "student_id": str(event.get("student_id") or ""),
                "decision": decision,
            }
        )
    return _pack(decisions, ("released", "suppressed", "malformed"), "released", "suppressed")


plan = plan_220
