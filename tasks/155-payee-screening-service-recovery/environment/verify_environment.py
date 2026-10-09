#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
from collections import Counter

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
sample = "item_id,decision\nR-1,pending_system\nR-2,blocked\n"
rows = list(csv.DictReader(io.StringIO(sample)))
counts = Counter(row["decision"] for row in rows)
if counts != {"pending_system": 1, "blocked": 1}:
    raise SystemExit("screening CSV reconciliation probe failed")
state = {
    "workflow_id": "155-payee-screening-service-recovery",
    "decision_counts": dict(sorted(counts.items())),
    "external_actions_executed": False,
}
encoded = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
if json.loads(encoded)["external_actions_executed"] is not False:
    raise SystemExit("screening JSON boolean probe failed")
if len(hashlib.sha256(encoded).hexdigest()) != 64:
    raise SystemExit("screening receipt digest probe failed")
print(json.dumps({
    "python3": "3.12",
    "csv": "passed",
    "counter": "passed",
    "json": "passed",
    "sha256": "passed",
    "services": "not_required_by_task_contract",
}, sort_keys=True))
