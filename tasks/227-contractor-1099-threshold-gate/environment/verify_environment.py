#!/usr/bin/env python3
"""Verify the shared agent runtime for 227-contractor-1099-threshold-gate."""

import decimal
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    payments = [decimal.Decimal('350.00'), decimal.Decimal('275.00')]
    assert sum(payments) == decimal.Decimal('625.00')
    print(json.dumps({"environment": "passed", "task_id": "227-contractor-1099-threshold-gate"}, sort_keys=True))


if __name__ == "__main__":
    main()
