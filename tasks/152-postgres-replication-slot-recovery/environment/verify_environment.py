#!/usr/bin/env python3
"""Task 152 is an offline planner; PostgreSQL client/server access is not required."""
from __future__ import annotations

import hashlib
import json
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
slots = [
    {"slot": "orders", "restart_lsn": 120, "confirmed_flush_lsn": 180},
    {"slot": "billing", "restart_lsn": 170, "confirmed_flush_lsn": 190},
]
primary_lsn = 220
retained = {
    row["slot"]: primary_lsn - row["restart_lsn"]
    for row in slots
}
if retained != {"orders": 100, "billing": 50}:
    raise SystemExit("PostgreSQL slot LSN arithmetic probe failed")
payload = json.dumps(
    {"retained_wal": retained, "postgres_runtime": "not_required_by_task_contract"},
    sort_keys=True,
).encode()
if len(hashlib.sha256(payload).hexdigest()) != 64:
    raise SystemExit("slot recovery hash probe failed")
print(json.dumps({"python3": "3.12", "lsn_arithmetic": "passed", "json": "passed", "sha256": "passed", "postgres_runtime": "not_required_by_task_contract"}, sort_keys=True))
