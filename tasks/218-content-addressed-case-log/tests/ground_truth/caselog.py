"""Trusted recomputation of the Aerowake content-addressed case log.

This module is grader-only. It never imports the agent-visible controller and
never reads candidate-authored artifacts as evidence.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

DECISIONS = ("recorded", "already_recorded", "conflict", "malformed")


def _counts(decisions: list[dict[str, Any]]) -> dict[str, int]:
    tallies = {name: 0 for name in DECISIONS}
    tallies.update(Counter(str(row["decision"]) for row in decisions))
    return tallies


def sha256_canonical(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def plan(batch: list[dict[str, Any]]) -> dict[str, Any]:
    seen_ids: set[str] = set()
    by_name: dict[str, str] = {}
    decisions: list[dict[str, Any]] = []
    recorded: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(batch):
        case_id = str(item.get("case_id") or "")
        name = str(item.get("name") or "")
        payload = item.get("payload")
        if not case_id or case_id in seen_ids or not name or not isinstance(payload, dict):
            decision = "malformed"
            digest = ""
        else:
            digest = sha256_canonical(payload)
            if name not in by_name:
                decision = "recorded"
                by_name[name] = digest
                recorded[name] = {
                    "name": name,
                    "digest": digest,
                    "case_id": case_id,
                    "payload": payload,
                }
            elif by_name[name] == digest:
                decision = "already_recorded"
            else:
                decision = "conflict"
        if case_id:
            seen_ids.add(case_id)
        decisions.append(
            {
                "index": index,
                "case_id": case_id,
                "name": name,
                "decision": decision,
                "digest": digest,
            }
        )
    return {
        "decisions": decisions,
        "counts": _counts(decisions),
        "cases": [recorded[name] for name in sorted(recorded)],
        "recorded_names": sorted(recorded),
    }
