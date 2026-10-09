#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import re
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

rows = list(csv.DictReader(io.StringIO("decision_id,evidence_ids\nDEC-4,OPS-61;PRIV-77\n")))
if rows != [{"decision_id": "DEC-4", "evidence_ids": "OPS-61;PRIV-77"}]:
    raise SystemExit("append-only CSV parsing probe failed")
evidence = set(re.findall(r"[A-Z]{2,}-\d+", rows[0]["evidence_ids"]))
if evidence != {"OPS-61", "PRIV-77"}:
    raise SystemExit("evidence-ID extraction probe failed")

plan = json.loads('{"ceiling":92000,"milestone_costs":[31000,34000,24000]}')
cost = sum(plan["milestone_costs"])
if cost != 89000 or cost > plan["ceiling"]:
    raise SystemExit("project budget reconciliation probe failed")

print(json.dumps({"python3": "3.12", "csv_json": "passed", "evidence_ids": "passed"}, sort_keys=True))
