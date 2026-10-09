#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import sys
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")

rows = list(csv.DictReader(io.StringIO(
    "payment_id,gross_amount,fee_amount,usd_rate\n"
    "P002,200.00,2.73,1.1000\n"
)))
totals: defaultdict[str, Decimal] = defaultdict(Decimal)
for row in rows:
    rate = Decimal(row["usd_rate"])
    gross = (Decimal(row["gross_amount"]) * rate).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    fee = (Decimal(row["fee_amount"]) * rate).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    totals["cash"] += gross - fee
    totals["fees"] += fee
if totals != {"cash": Decimal("217.00"), "fees": Decimal("3.00")}:
    raise SystemExit(f"financial close Decimal probe failed: {dict(totals)!r}")

print(json.dumps({"python3": "3.12", "csv_decimal": "passed", "account_totals": "passed"}, sort_keys=True))
