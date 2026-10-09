#!/usr/bin/env python3
"""Verify the shared agent runtime for 244-aircraft-weight-balance-loadsheet."""

import datetime
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    purchased = datetime.date(2025, 1, 1)
    requested = datetime.date(2026, 1, 1)
    assert (requested - purchased).days == 365
    print(json.dumps({"environment": "passed", "task_id": '244-aircraft-weight-balance-loadsheet'}, sort_keys=True))


if __name__ == "__main__":
    main()
