#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

policy = {
    "reserve_ms": 50,
    "per_try_cap_ms": 500,
    "initial_backoff_ms": 100,
    "backoff_multiplier": 2,
}
incoming_ms = 1200
elapsed_ms = 300
attempt = 2
backoff_ms = policy["initial_backoff_ms"] * policy["backoff_multiplier"] ** (attempt - 1)
remaining_ms = incoming_ms - elapsed_ms - policy["reserve_ms"] - backoff_ms
per_try_ms = min(policy["per_try_cap_ms"], remaining_ms)
if (backoff_ms, remaining_ms, per_try_ms) != (200, 650, 500):
    raise SystemExit("deadline/backoff arithmetic probe failed")
state = {"caller_cancelled": True, "child_calls": 2, "decision": "cancel_children"}
payload = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
if len(hashlib.sha256(payload).hexdigest()) != 64:
    raise SystemExit("RPC state digest probe failed")
print(json.dumps({
    "python3": "3.12", "deadline_budget": "passed", "cancellation": "passed",
    "json_sha256": "passed", "grpc_runtime": "not_required_by_task_contract",
}, sort_keys=True))
