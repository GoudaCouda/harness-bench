#!/usr/bin/env python3
"""Verify the shared agent runtime for 224-sla-refund-chargeback-gate."""

import decimal
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    amount = decimal.Decimal('19.99') * decimal.Decimal('0.10')
    assert amount.quantize(decimal.Decimal('0.01')) == decimal.Decimal('2.00')
    print(json.dumps({"environment": "passed", "task_id": "224-sla-refund-chargeback-gate"}, sort_keys=True))


if __name__ == "__main__":
    main()
