#!/usr/bin/env python3
"""Verify the shared agent runtime for 215-placement-inventory-union."""

import collections
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    inventory = collections.defaultdict(set)
    inventory['rack-a'].update({'host-1', 'host-2'})
    assert len(inventory['rack-a']) == 2
    print(json.dumps({"environment": "passed", "task_id": "215-placement-inventory-union"}, sort_keys=True))


if __name__ == "__main__":
    main()
