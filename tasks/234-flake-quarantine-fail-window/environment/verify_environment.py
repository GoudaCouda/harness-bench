#!/usr/bin/env python3
"""Verify the shared agent runtime for 234-flake-quarantine-fail-window."""

import collections
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    runs = collections.deque([True, False, True, False], maxlen=4)
    assert sum(not value for value in runs) == 2
    print(json.dumps({"environment": "passed", "task_id": "234-flake-quarantine-fail-window"}, sort_keys=True))


if __name__ == "__main__":
    main()
