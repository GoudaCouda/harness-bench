#!/usr/bin/env python3
"""Verify the shared agent runtime for 221-loto-energize-tag-gate."""

import collections
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    tags = collections.Counter(['applied', 'verified', 'applied'])
    assert tags['applied'] == 2 and tags['verified'] == 1
    print(json.dumps({"environment": "passed", "task_id": "221-loto-energize-tag-gate"}, sort_keys=True))


if __name__ == "__main__":
    main()
