"""Trusted recomputation of Admit DNS cache rows only for in-zone positive answers with a live TTL.

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

def plan_233(events: list[dict[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    decisions: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        item_id = str(event.get("qname") or "")
        rcode = str(event.get("rcode") or "")
        ttl = int(event.get("ttl") or 0)
        cname_loop = bool(event.get("cname_loop"))
        in_zone = bool(event.get("in_zone"))
        if _malformed(event, seen, "qname", "qtype") or cname_loop:
            decision = "malformed"
        elif rcode == "NXDOMAIN" or ttl <= 0 or not in_zone:
            decision = "held"
        else:
            decision = "admitted"
        if item_id:
            seen.add(item_id)
        decisions.append(
            {
                "index": index,
                "item_id": item_id,
                "qtype": str(event.get("qtype") or ""),
                "decision": decision,
            }
        )
    return _pack(decisions, ("admitted", "held", "malformed"), "admitted", "held")


plan = plan_233
