#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")

rows = list(csv.DictReader(io.StringIO(
    "timestamp,service,requests,z_error_rate,revenue_impact_usd\n"
    "2026-04-20T10:00:00Z,checkout,970,8.4,780.00\n"
)))
row = rows[0]
stamp = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
causes = Counter(["deployment", "deployment", "unattributed"])
impact = sum((Decimal(row["revenue_impact_usd"]), Decimal("620.50")), Decimal("0"))
if (
    stamp.astimezone(timezone.utc).isoformat() != "2026-04-20T10:00:00+00:00"
    or abs(Decimal(row["z_error_rate"])) < Decimal("6")
    or impact != Decimal("1400.50")
    or causes != {"deployment": 2, "unattributed": 1}
):
    raise SystemExit("anomaly attribution reconciliation probe failed")

print(json.dumps({"python3": "3.12", "csv_time_decimal": "passed", "counter": "passed"}, sort_keys=True))
