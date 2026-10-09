"""Trusted recomputation of Record usage only inside the licensed ISRC territory window.

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

def plan_223(events: list[dict[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    seen_isrc: dict[str, str] = {}
    decisions: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        item_id = str(event.get("usage_id") or "")
        isrc = str(event.get("isrc") or "")
        title = str(event.get("title") or "")
        territory = str(event.get("territory") or "")
        allowed = {item.strip() for item in str(event.get("allowed_territories") or "").split(",") if item.strip()}
        if _malformed(event, seen, "usage_id", "isrc") or not territory:
            decision = "malformed"
        elif isrc in seen_isrc and seen_isrc[isrc] != title:
            decision = "conflict"
        elif territory not in allowed:
            decision = "conflict"
        else:
            decision = "recorded"
            seen_isrc.setdefault(isrc, title)
        if item_id:
            seen.add(item_id)
        decisions.append(
            {
                "index": index,
                "item_id": item_id,
                "isrc": isrc,
                "decision": decision,
            }
        )
    return _pack(decisions, ("recorded", "conflict", "malformed"), "recorded", "conflict")


plan = plan_223
