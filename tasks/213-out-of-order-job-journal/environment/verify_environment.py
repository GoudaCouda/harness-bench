#!/usr/bin/env python3
"""Verify the shared agent runtime for 213-out-of-order-job-journal."""

import datetime
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    times = [datetime.datetime.fromisoformat(value) for value in ('2026-01-01T00:00:02+00:00', '2026-01-01T00:00:01+00:00')]
    assert sorted(times)[0].second == 1
    print(json.dumps({"environment": "passed", "task_id": "213-out-of-order-job-journal"}, sort_keys=True))


if __name__ == "__main__":
    main()
