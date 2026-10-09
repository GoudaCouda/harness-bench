#!/usr/bin/env python3
"""Verify the shared agent runtime for 222-medication-refill-window-gate."""

import datetime
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    filled = datetime.date(2026, 1, 1)
    assert filled + datetime.timedelta(days=30) == datetime.date(2026, 1, 31)
    print(json.dumps({"environment": "passed", "task_id": "222-medication-refill-window-gate"}, sort_keys=True))


if __name__ == "__main__":
    main()
