#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import io
import json
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
filing = {
    "entity": {"cik": "0000123456"},
    "facts": [{"name": "Revenue", "value": 1250000, "context": "C-YEAR"}],
}
pretty = json.dumps(filing, indent=2)
compact = json.dumps(filing, separators=(",", ":"))
canonical = lambda text: hashlib.sha256(
    json.dumps(json.loads(text), sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
if canonical(pretty) != canonical(compact):
    raise SystemExit("logical filing digest is formatting-dependent")
rows = list(csv.DictReader(io.StringIO(
    "issue_id,severity,action,target,new_value,status,evidence_refs\n"
    "E-CIK,error,normalize,entity.cik,0000123456,resolved,rulebook.md\n"
)))
if len(rows) != 1 or rows[0]["issue_id"] != "E-CIK":
    raise SystemExit("repair ledger CSV probe failed")
print(json.dumps({
    "python3": "3.12", "json": "passed", "canonical_sha256": "passed",
    "csv": "passed", "services": "not_required_by_task_contract",
}, sort_keys=True))
