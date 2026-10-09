#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import sys
import tempfile
from decimal import Decimal
from pathlib import Path


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

header = ["invoice_line_id", "approved_amount", "held_amount"]
raw = "invoice_line_id,approved_amount,held_amount\nIL-01,97.50,02.50\n"
rows = list(csv.DictReader(raw.splitlines()))
if list(rows[0]) != header or rows[0]["invoice_line_id"] != "IL-01":
    raise SystemExit("strict invoice CSV parsing probe failed")
if Decimal(rows[0]["approved_amount"]) + Decimal(rows[0]["held_amount"]) != Decimal("100.00"):
    raise SystemExit("exact-cent invoice reconciliation probe failed")

with tempfile.TemporaryDirectory(prefix="hb-ap-control-probe-") as temporary:
    root = Path(temporary)
    candidate = root / "payables_control.json"
    staged = root / ".payables_control.json.tmp"
    staged.write_text(json.dumps({"execution_state": "review_only"}) + "\n", encoding="utf-8")
    staged.replace(candidate)
    parsed = json.loads(candidate.read_text(encoding="utf-8"))
    if parsed != {"execution_state": "review_only"}:
        raise SystemExit("atomic AP control-file probe failed")
    digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
    if len(digest) != 64:
        raise SystemExit("AP review artifact hash probe failed")

print(
    json.dumps(
        {"python3": "3.12", "csv": "passed", "decimal": "passed", "atomic_replace": "passed", "sha256": "passed"},
        sort_keys=True,
    )
)
