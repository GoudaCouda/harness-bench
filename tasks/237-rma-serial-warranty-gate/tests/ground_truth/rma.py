"""Trusted recomputation of Record RMAs only for in-warranty serials that match a single SKU.

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

def plan_237(events: list[dict[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    seen_serial: dict[str, str] = {}
    decisions: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        item_id = str(event.get("rma_id") or "")
        serial = str(event.get("serial") or "")
        sku = str(event.get("sku") or "")
        in_warranty = bool(event.get("in_warranty"))
        condition = str(event.get("condition") or "")
        if _malformed(event, seen, "rma_id", "serial"):
            decision = "malformed"
        elif serial in seen_serial and seen_serial[serial] != sku:
            decision = "conflict"
        elif not in_warranty or condition == "open_box":
            decision = "conflict"
        else:
            decision = "recorded"
            seen_serial.setdefault(serial, sku)
        if item_id:
            seen.add(item_id)
        decisions.append(
            {
                "index": index,
                "item_id": item_id,
                "serial": serial,
                "decision": decision,
            }
        )
    return _pack(decisions, ("recorded", "conflict", "malformed"), "recorded", "conflict")


plan = plan_237
