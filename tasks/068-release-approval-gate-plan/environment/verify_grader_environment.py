#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import re
import sys

from harnessbench.grading.legacy_case_adapter import grouped_observations, checks_by_id

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

rows = list(
    csv.DictReader(
        io.StringIO(
            "blocker_id,severity,owner_role\n"
            "RR-CANARY,critical,sre_lead\n"
        )
    )
)
if rows[0]["blocker_id"] != "RR-CANARY" or not re.search(r"canary", json.dumps(rows), re.IGNORECASE):
    raise SystemExit("blocker CSV/JSON/regex probe failed")

private = {
    "checks": [
        {"id": "blocker_RR-CANARY", "pass": True},
        {"id": "packet_decision", "pass": True},
    ]
}
observed = grouped_observations(
    private,
    {
        "technical_blocker": ["blocker_RR-CANARY"],
        "decision": ["packet_decision"],
    },
)
if not all(item["pass"] for item in observed.values()):
    raise SystemExit("legacy case grouping probe failed")
if set(checks_by_id(private)) != {"blocker_RR-CANARY", "packet_decision"}:
    raise SystemExit("legacy check indexing probe failed")

print(json.dumps({"python3": "3.10", "csv_json_regex": "passed", "case_adapter": "passed"}, sort_keys=True))
