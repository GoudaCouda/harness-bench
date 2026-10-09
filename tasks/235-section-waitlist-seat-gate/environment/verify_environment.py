#!/usr/bin/env python3
"""Verify the shared agent runtime for 235-section-waitlist-seat-gate."""

import collections
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    waitlist = collections.deque(['student-a', 'student-b'])
    assert waitlist.popleft() == 'student-a'
    print(json.dumps({"environment": "passed", "task_id": "235-section-waitlist-seat-gate"}, sort_keys=True))


if __name__ == "__main__":
    main()
