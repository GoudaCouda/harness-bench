#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import sys
from datetime import datetime

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")

queue = """request_id,received_at,requester_type,target_account_id
DSAR-203,2026-05-18T09:41:00Z,self,acct_1003
"""
row = next(csv.DictReader(io.StringIO(queue)))
received = datetime.fromisoformat(row["received_at"])
if row["request_id"] != "DSAR-203" or received.utcoffset() is None:
    raise SystemExit("DSAR queue timestamp probe failed")

evidence = {
    "request_id": "DSAR-204",
    "agent_identity_check": {"status": "completed"},
    "authorization": {
        "holder_account_id": "acct_1004",
        "authorized_action": "delete_personal_data",
    },
}
decoded = json.loads(json.dumps(evidence, sort_keys=True))
if decoded["authorization"]["authorized_action"] != "delete_personal_data":
    raise SystemExit("authority-evidence JSON probe failed")

systems = {part for part in "profile_store;support_history".split(";") if part}
if systems != {"profile_store", "support_history"}:
    raise SystemExit("semicolon system-set probe failed")

print(
    json.dumps(
        {
            "python3": "3.12",
            "csv_queue": "passed",
            "iso_timestamp": "passed",
            "json_authority": "passed",
            "system_sets": "passed",
        },
        sort_keys=True,
    )
)
