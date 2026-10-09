#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from decimal import Decimal

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
if Decimal("1.005").quantize(Decimal("0.01")) != Decimal("1.00"):
    raise SystemExit("decimal probe failed")
if datetime.strptime("10-Jan-2025", "%d-%b-%Y").date().isoformat() != "2025-01-10":
    raise SystemExit("date parsing probe failed")
if next(csv.DictReader(["a,b", "1,2"])) != {"a": "1", "b": "2"}:
    raise SystemExit("CSV probe failed")
print(json.dumps({"python": "3.12", "stdlib": ["csv", "datetime", "decimal"]}))
