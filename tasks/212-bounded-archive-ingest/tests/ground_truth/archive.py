"""Trusted recomputation of the Northline bounded archive ingest."""

from __future__ import annotations

import hashlib
import json
from typing import Any

DECISION_INGESTED = "ingested"
DECISION_REPLAYED = "replayed"
DECISION_CONFLICT = "conflict"
DECISION_CHECKSUM_MISMATCH = "checksum_mismatch"
DECISION_CAPACITY_EXCEEDED = "capacity_exceeded"
DECISION_REJECTED = "rejected"

DECISIONS = (
    DECISION_INGESTED,
    DECISION_REPLAYED,
    DECISION_CONFLICT,
    DECISION_CHECKSUM_MISMATCH,
    DECISION_CAPACITY_EXCEEDED,
    DECISION_REJECTED,
)


def checksum_of(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def archive_bytes(objects: dict[str, Any]) -> int:
    return sum(int(item.get("bytes") or 0) for item in objects.values())


def evict_until_fit(
    objects: dict[str, Any],
    incoming_bytes: int,
    max_bytes: int,
    max_objects: int,
) -> list[str]:
    """Evict oldest unpinned objects until the incoming object fits.

    Returns the evicted ids. If the object still cannot fit after every
    unpinned object is gone, the archive is left unchanged and the caller
    must refuse the ingest.
    """

    working = json.loads(json.dumps(objects))
    evicted: list[str] = []

    def fits() -> bool:
        n = len(working)
        used = archive_bytes(working)
        return n + 1 <= max_objects and used + incoming_bytes <= max_bytes

    while not fits():
        candidates = [
            (int(item.get("ingested_at") or 0), object_id)
            for object_id, item in working.items()
            if not bool(item.get("pinned"))
        ]
        if not candidates:
            return evicted
        candidates.sort()
        victim = candidates[0][1]
        del working[victim]
        evicted.append(victim)
        objects.clear()
        objects.update(working)
    return evicted


def decide_one(
    item: dict[str, Any],
    objects: dict[str, Any],
    clock: int,
    max_bytes: int,
    max_objects: int,
) -> dict[str, Any]:
    object_id = item.get("object_id")
    content = item.get("content")
    claimed = item.get("checksum")
    pinned = bool(item.get("pinned"))
    if not isinstance(object_id, str) or not isinstance(content, str) or not isinstance(claimed, str):
        return {
            "object_id": object_id,
            "decision": DECISION_REJECTED,
            "reason": "malformed_object",
        }
    actual = checksum_of(content)
    size = len(content.encode("utf-8"))
    if claimed != actual:
        return {
            "object_id": object_id,
            "decision": DECISION_CHECKSUM_MISMATCH,
            "reason": "claimed_checksum_does_not_match_content",
        }
    existing = objects.get(object_id)
    if isinstance(existing, dict):
        if existing.get("checksum") == actual:
            return {
                "object_id": object_id,
                "decision": DECISION_REPLAYED,
                "reason": "identical_object_already_present",
            }
        return {
            "object_id": object_id,
            "decision": DECISION_CONFLICT,
            "reason": "object_id_reused_with_different_checksum",
        }

    snapshot = json.loads(json.dumps(objects))
    evicted = evict_until_fit(objects, size, max_bytes, max_objects)
    if len(objects) + 1 > max_objects or archive_bytes(objects) + size > max_bytes:
        objects.clear()
        objects.update(snapshot)
        return {
            "object_id": object_id,
            "decision": DECISION_CAPACITY_EXCEEDED,
            "reason": "cannot_fit_after_evicting_unpinned_objects",
        }
    objects[object_id] = {
        "bytes": size,
        "checksum": actual,
        "pinned": pinned,
        "ingested_at": clock,
        "content": content,
    }
    return {
        "object_id": object_id,
        "decision": DECISION_INGESTED,
        "reason": "accepted_after_eviction" if evicted else "accepted_with_capacity",
        "evicted": evicted,
        "bytes": size,
    }


def plan(
    seed_objects: dict[str, Any],
    staging: list[dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    clock = int(policy["archive_clock_epoch"])
    max_bytes = int(policy["max_bytes"])
    max_objects = int(policy["max_objects"])
    objects = json.loads(json.dumps(seed_objects))
    decisions: list[dict[str, Any]] = []
    evicted_all: list[str] = []
    for item in staging:
        decision = decide_one(item, objects, clock, max_bytes, max_objects)
        decisions.append(decision)
        evicted_all.extend(decision.get("evicted") or [])

    counts = {name: 0 for name in DECISIONS}
    for entry in decisions:
        counts[entry["decision"]] += 1

    public_objects = {
        object_id: {
            "bytes": record["bytes"],
            "checksum": record["checksum"],
            "pinned": record["pinned"],
            "ingested_at": record["ingested_at"],
        }
        for object_id, record in objects.items()
    }
    return {
        "final_objects": {key: public_objects[key] for key in sorted(public_objects)},
        "final_contents": {key: objects[key]["content"] for key in sorted(objects)},
        "decisions": decisions,
        "counts": counts,
        "evicted": evicted_all,
        "used_bytes": archive_bytes(objects),
        "used_objects": len(objects),
    }
