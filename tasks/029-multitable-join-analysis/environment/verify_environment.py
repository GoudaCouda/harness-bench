#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import sys
from decimal import Decimal

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

orders = list(
    csv.DictReader(
        io.StringIO(
            "order_id,customer_id,gross,discount\n"
            "O-1,C-01,105.25,5.25\n"
            "O-2,C-01,20.00,0.00\n"
        )
    )
)
net = sum(
    (Decimal(row["gross"]) - Decimal(row["discount"]) for row in orders),
    Decimal("0"),
)
refund = Decimal("4.50")
if (net - refund).quantize(Decimal("0.01")) != Decimal("115.50"):
    raise SystemExit("CSV/Decimal reconciliation probe failed")

print(
    json.dumps(
        {
            "python3": "3.12",
            "stdlib": ["csv", "decimal", "json"],
            "reconciled_net": "115.50",
        },
        sort_keys=True,
    )
)
