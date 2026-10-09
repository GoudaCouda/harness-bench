#!/usr/bin/env python3
"""Verify the shared agent runtime for 238-gtfs-realtime-vs-static-reconcile."""

import datetime
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    purchased = datetime.date(2025, 1, 1)
    requested = datetime.date(2026, 1, 1)
    assert (requested - purchased).days == 365
    print(json.dumps({"environment": "passed", "task_id": '238-gtfs-realtime-vs-static-reconcile'}, sort_keys=True))


if __name__ == "__main__":
    main()
