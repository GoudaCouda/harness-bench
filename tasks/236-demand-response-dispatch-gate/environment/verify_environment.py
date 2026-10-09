#!/usr/bin/env python3
"""Verify the shared agent runtime for 236-demand-response-dispatch-gate."""

import decimal
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    capacity = decimal.Decimal('100')
    committed = decimal.Decimal('72.5')
    assert capacity - committed == decimal.Decimal('27.5')
    print(json.dumps({"environment": "passed", "task_id": "236-demand-response-dispatch-gate"}, sort_keys=True))


if __name__ == "__main__":
    main()
