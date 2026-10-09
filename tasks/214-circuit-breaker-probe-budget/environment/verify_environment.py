#!/usr/bin/env python3
"""Verify the shared agent runtime for 214-circuit-breaker-probe-budget."""

import collections
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    states = collections.Counter(['closed', 'half_open', 'closed'])
    assert states['closed'] == 2
    print(json.dumps({"environment": "passed", "task_id": "214-circuit-breaker-probe-budget"}, sort_keys=True))


if __name__ == "__main__":
    main()
