#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import sys
from datetime import date

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")

rules = {
    "priority_order": ["emergency_addendum", "regional_addendum", "global_policy"],
    "effective_dates": {"emergency_addendum": "2025-03-01"},
    "scopes": {"regional_addendum": ["FR"]},
}
round_trip = json.loads(json.dumps(rules, sort_keys=True))
if round_trip["priority_order"][0] != "emergency_addendum":
    raise SystemExit("JSON precedence-order probe failed")
if date.fromisoformat(round_trip["effective_dates"]["emergency_addendum"]) != date(2025, 3, 1):
    raise SystemExit("ISO effective-date probe failed")

buf = io.StringIO(newline="")
writer = csv.DictWriter(
    buf,
    fieldnames=[
        "case_id",
        "claim_axis",
        "winning_source",
        "losing_sources",
        "priority_rule",
        "coverage_scope",
    ],
)
writer.writeheader()
writer.writerow(
    {
        "case_id": "C-001",
        "claim_axis": "expense_cap",
        "winning_source": "emergency_addendum_2025-03.md",
        "losing_sources": "expense_policy_2025-02.md",
        "priority_rule": "version_priority",
        "coverage_scope": "global",
    }
)
parsed = list(csv.DictReader(io.StringIO(buf.getvalue())))
if len(parsed) != 1 or parsed[0]["priority_rule"] != "version_priority":
    raise SystemExit("conflict-audit CSV round-trip probe failed")

print(
    json.dumps(
        {
            "python3": "3.12",
            "json_precedence": "passed",
            "iso_dates": "passed",
            "csv_audit": "passed",
        },
        sort_keys=True,
    )
)
