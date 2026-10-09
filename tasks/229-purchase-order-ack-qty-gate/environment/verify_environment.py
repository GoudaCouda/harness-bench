#!/usr/bin/env python3
"""Verify the shared agent runtime for 229-purchase-order-ack-qty-gate."""

import decimal
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    ordered = decimal.Decimal('12')
    acknowledged = decimal.Decimal('10')
    assert ordered - acknowledged == 2
    print(json.dumps({"environment": "passed", "task_id": "229-purchase-order-ack-qty-gate"}, sort_keys=True))


if __name__ == "__main__":
    main()
