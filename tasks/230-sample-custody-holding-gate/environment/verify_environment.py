#!/usr/bin/env python3
"""Verify the shared agent runtime for 230-sample-custody-holding-gate."""

import datetime
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    collected = datetime.datetime.fromisoformat('2026-01-01T10:00:00+00:00')
    received = datetime.datetime.fromisoformat('2026-01-01T11:30:00+00:00')
    assert received > collected
    print(json.dumps({"environment": "passed", "task_id": "230-sample-custody-holding-gate"}, sort_keys=True))


if __name__ == "__main__":
    main()
