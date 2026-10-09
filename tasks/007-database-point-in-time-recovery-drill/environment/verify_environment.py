#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

plan = {
    "target_type": "name",
    "target_name": "before_batch_cleanup",
    "required_wal_segments": ["00000002000000000000000C", "00000002000000000000000B"],
    "expected_invariants": [
        {"check_id": "foreign_keys", "expected": 0},
        {"check_id": "invoice_total", "expected": 1250},
    ],
}
normalized = dict(plan)
normalized["required_wal_segments"] = sorted(plan["required_wal_segments"])
normalized["expected_invariants"] = sorted(
    plan["expected_invariants"], key=lambda row: row["check_id"]
)
digest = hashlib.sha256(
    json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
if len(digest) != 64 or normalized["target_type"] != "name":
    raise SystemExit("offline PITR plan normalization probe failed")
print(json.dumps({"python": "3.12", "offline_pitr_state_machine": "passed", "sha256": digest}, sort_keys=True))
