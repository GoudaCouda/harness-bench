#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import sys
from decimal import Decimal

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")

table = """metric,cohort,value,unit,p_value
retention_lift,overall,7.4,percentage_points,0.031
retention_lift,mobile,9.1,percentage_points,0.018
retention_lift,partner,-1.0,percentage_points,0.410
"""
rows = list(csv.DictReader(io.StringIO(table)))
values = {row["cohort"]: Decimal(row["value"]) for row in rows}
if max(values, key=values.get) != "mobile" or values["partner"] >= 0:
    raise SystemExit("numeric cohort-comparison probe failed")

audit = io.StringIO(newline="")
writer = csv.writer(audit)
writer.writerow(
    [
        "claim_id",
        "claim_text",
        "status",
        "primary_source",
        "evidence_location",
        "evidence_signal",
        "secondary_sources",
        "rationale",
    ]
)
writer.writerow(
    [
        "CL-02",
        "Every cohort improved",
        "contradicted",
        "sources/results_table.csv",
        "retention_lift/partner",
        "partner value is -1.0",
        "sources/peer_review_notes.md",
        "negative cohort refutes the universal claim",
    ]
)
parsed = list(csv.DictReader(io.StringIO(audit.getvalue())))
if len(parsed) != 1 or parsed[0]["status"] != "contradicted":
    raise SystemExit("claim-audit CSV round-trip probe failed")

matrix = {
    "claims": [
        {
            "claim_id": "CL-02",
            "status": "contradicted",
            "evidence": {
                "source_file": "sources/results_table.csv",
                "location": "retention_lift/partner",
                "supports_or_refutes": "refutes",
                "signal": "partner value is -1.0",
            },
            "reproducibility_note": "direct table comparison",
        }
    ]
}
if json.loads(json.dumps(matrix, sort_keys=True))["claims"][0]["evidence"]["supports_or_refutes"] != "refutes":
    raise SystemExit("evidence-matrix JSON round-trip probe failed")

print(
    json.dumps(
        {
            "python3": "3.12",
            "csv_audit": "passed",
            "decimal_comparison": "passed",
            "json_evidence_matrix": "passed",
        },
        sort_keys=True,
    )
)
