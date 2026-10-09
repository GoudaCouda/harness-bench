"""Trusted recomputation of the Shorefront dataset-manifest pin gate.

This module is grader-only. It never imports the agent-visible controller and
never reads candidate-authored artifacts as evidence.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

DECISIONS = (
    "ingested",
    "updated",
    "pin_protected",
    "digest_mismatch",
    "rejected_scheme",
    "malformed",
)


def _counts(decisions: list[dict[str, Any]]) -> dict[str, int]:
    tallies = {name: 0 for name in DECISIONS}
    tallies.update(Counter(str(row["decision"]) for row in decisions))
    return tallies


def plan(seed: dict[str, Any], queue: list[dict[str, Any]]) -> dict[str, Any]:
    catalog = {key: dict(value) for key, value in (seed.get("datasets") or {}).items()}
    seen_ids: set[str] = set()
    decisions: list[dict[str, Any]] = []
    for index, item in enumerate(queue):
        dataset_id = str(item.get("dataset_id") or "")
        uri = str(item.get("uri") or "")
        digest = str(item.get("sha256") or "")
        claimed = str(item.get("claimed_sha256") or digest)
        if not dataset_id or dataset_id in seen_ids or not uri or not digest:
            decision = "malformed"
        elif claimed != digest:
            decision = "digest_mismatch"
        elif not (uri.startswith("https://") or uri.startswith("file://")):
            decision = "rejected_scheme"
        elif dataset_id in catalog and bool(catalog[dataset_id].get("pinned")):
            decision = "pin_protected"
        elif dataset_id in catalog:
            decision = "updated"
            catalog[dataset_id] = {
                "dataset_id": dataset_id,
                "uri": uri,
                "sha256": digest,
                "pinned": bool(item.get("pinned")),
            }
        else:
            decision = "ingested"
            catalog[dataset_id] = {
                "dataset_id": dataset_id,
                "uri": uri,
                "sha256": digest,
                "pinned": bool(item.get("pinned")),
            }
        if dataset_id:
            seen_ids.add(dataset_id)
        decisions.append(
            {
                "index": index,
                "request_id": item.get("request_id"),
                "dataset_id": dataset_id,
                "decision": decision,
            }
        )
    pinned_ids = sorted(key for key, row in catalog.items() if bool(row.get("pinned")))
    return {
        "decisions": decisions,
        "counts": _counts(decisions),
        "datasets": catalog,
        "dataset_ids": sorted(catalog),
        "pinned_ids": pinned_ids,
    }
