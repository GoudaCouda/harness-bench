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
            "job,classification,action,final_attempt,final_status,evidence\n"
            "macos,runner_retry_exhausted,escalate_runner,2,runner_lost,retry_update.json:macos\n"
        )
    )
)
if rows[0]["final_attempt"] != "2" or not re.search(r"runner.*exhaust", json.dumps(rows), re.IGNORECASE):
    raise SystemExit("CI ledger CSV/JSON/regex probe failed")

private = {
    "checks": [
        {"id": "ledger_item_1", "pass": True},
        {"id": "aggregate_state", "pass": True},
    ]
}
observed = grouped_observations(
    private,
    {
        "job_recovery": ["ledger_item_1"],
        "aggregate": ["aggregate_state"],
    },
)
if not all(item["pass"] for item in observed.values()):
    raise SystemExit("legacy case grouping probe failed")
if set(checks_by_id(private)) != {"ledger_item_1", "aggregate_state"}:
    raise SystemExit("legacy check indexing probe failed")

print(json.dumps({"python3": "3.10", "csv_json_regex": "passed", "case_adapter": "passed"}, sort_keys=True))
