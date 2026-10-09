"""Trusted recomputation of the Ridgepeak placement inventory union.

This module is grader-only. It never imports the agent-visible controller and
never reads candidate-authored artifacts as evidence.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

DECISIONS = ("selected", "dropped", "tombstoned")
SOURCE_RANK = {"started": 0, "waiting": 1, "running": 2}


def _counts(decisions: list[dict[str, Any]]) -> dict[str, int]:
    tallies = {name: 0 for name in DECISIONS}
    tallies.update(Counter(str(row["decision"]) for row in decisions))
    return tallies


def plan(snapshots: dict[str, list[dict[str, Any]]], *, limit: int = 4) -> dict[str, Any]:
    merged: dict[str, dict[str, Any]] = {}
    for source in ("started", "waiting", "running"):
        for item in snapshots.get(source) or []:
            region_id = str(item.get("region_id") or "")
            if not region_id:
                continue
            current = merged.get(region_id)
            if current is None or SOURCE_RANK[source] >= SOURCE_RANK[str(current.get("source"))]:
                merged[region_id] = {
                    "region_id": region_id,
                    "status": str(item.get("status")),
                    "source": source,
                }
    filtered = [row for row in merged.values() if row["status"] != "tombstone"]
    filtered.sort(key=lambda row: row["region_id"])
    selected = filtered[:limit]
    dropped = [row["region_id"] for row in filtered[limit:]]
    tombstoned = sorted(
        region_id for region_id, row in merged.items() if row["status"] == "tombstone"
    )
    dropped_set = set(dropped)
    decisions: list[dict[str, Any]] = []
    for index, region_id in enumerate(sorted(merged)):
        row = merged[region_id]
        if row["status"] == "tombstone":
            decision = "tombstoned"
        elif region_id in dropped_set:
            decision = "dropped"
        else:
            decision = "selected"
        decisions.append(
            {
                "index": index,
                "region_id": region_id,
                "status": row["status"],
                "source": row["source"],
                "decision": decision,
            }
        )
    return {
        "decisions": decisions,
        "counts": _counts(decisions),
        "items": selected,
        "selected_ids": [row["region_id"] for row in selected],
        "dropped_ids": dropped,
        "tombstoned_ids": tombstoned,
        "item_count": len(selected),
        "union_count": len(filtered),
    }
