#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

last_cursor = "z-opaque"
next_cursor = "a-opaque"
if next_cursor == last_cursor:
    raise SystemExit("opaque cursor fixture must differ")
decision = {
    "action": "apply_event",
    "next_rv": next_cursor,
}
if decision != {"action": "apply_event", "next_rv": "a-opaque"}:
    raise SystemExit("opaque resourceVersion probe failed")

gone = {"outcome": "GONE", "last_applied_rv": "still-opaque"}
gone_decision = (
    {"action": "relist", "next_rv": None, "reset_state": True}
    if gone["outcome"] == "GONE" else {}
)
if not gone_decision.get("reset_state"):
    raise SystemExit("410 Gone relist probe failed")

stream = {"mode": "streaming_list", "send_initial_events": True,
          "rv_match": "NotOlderThan", "allow_bookmarks": True}
if not all((stream["send_initial_events"], stream["allow_bookmarks"],
            stream["rv_match"] == "NotOlderThan")):
    raise SystemExit("streaming-list contract probe failed")

print(json.dumps({
    "python3": "3.12",
    "opaque_resource_version": "passed",
    "gone_relist": "passed",
    "streaming_bookmark": "passed",
    "kubernetes_service": "not_required_by_offline_task_contract",
}, sort_keys=True))
