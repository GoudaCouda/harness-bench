#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import sys
from decimal import Decimal, ROUND_HALF_UP

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")

old_rows = list(csv.DictReader(io.StringIO("metric_name,value\narr,100000.0000\n")))
new_rows = list(csv.DictReader(io.StringIO("metric_name,value\narr,92000.0000\n")))
old = Decimal(old_rows[0]["value"])
new = Decimal(new_rows[0]["value"])
absolute = abs(new - old).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
relative = ((new - old) / abs(old)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
summary = {"metric_name": "arr", "absolute_diff": str(absolute), "relative_diff": str(relative)}
if json.loads(json.dumps(summary, sort_keys=True)) != {
    "metric_name": "arr",
    "absolute_diff": "8000.0000",
    "relative_diff": "-0.0800",
}:
    raise SystemExit(f"metric migration arithmetic probe failed: {summary!r}")

print(json.dumps({"python3": "3.12", "csv_decimal": "passed", "signed_relative_diff": "passed"}, sort_keys=True))
