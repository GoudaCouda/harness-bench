#!/usr/bin/env python3
"""Verify the shared agent runtime for 211-sliding-window-quota-ledger."""

import collections
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    window = collections.deque([2, 3], maxlen=2)
    window.append(5)
    assert list(window) == [3, 5]
    print(json.dumps({"environment": "passed", "task_id": "211-sliding-window-quota-ledger"}, sort_keys=True))


if __name__ == "__main__":
    main()
