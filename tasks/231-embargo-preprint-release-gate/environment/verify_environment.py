#!/usr/bin/env python3
"""Verify the shared agent runtime for 231-embargo-preprint-release-gate."""

import datetime
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    embargo = datetime.datetime.fromisoformat('2026-06-01T00:00:00+00:00')
    now = datetime.datetime.fromisoformat('2026-05-31T23:59:59+00:00')
    assert now < embargo
    print(json.dumps({"environment": "passed", "task_id": "231-embargo-preprint-release-gate"}, sort_keys=True))


if __name__ == "__main__":
    main()
