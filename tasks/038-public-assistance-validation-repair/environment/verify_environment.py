#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from decimal import Decimal

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

review = {"lines": [
    {"gross": "120000.00", "reductions": ["30000.00"], "status": "ready_with_reduction"},
    {"gross": "25000.00", "reductions": ["5000.00"], "status": "ready_with_reduction"},
]}
gross = sum((Decimal(row["gross"]) for row in review["lines"]), Decimal("0"))
reductions = sum((Decimal(value) for row in review["lines"] for value in row["reductions"]), Decimal("0"))
staged = gross - reductions
fingerprint = hashlib.sha256(json.dumps(review, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
if staged != Decimal("110000.00"):
    raise SystemExit("grant control-total probe failed")
if len(fingerprint) != 64:
    raise SystemExit("grant receipt digest probe failed")

print(json.dumps({"python3": "3.12", "decimal_totals": "passed", "sha256_receipt": "passed"}, sort_keys=True))
