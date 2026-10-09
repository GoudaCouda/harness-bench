#!/usr/bin/env python3
"""Verify the shared agent runtime for 232-gpc-cookie-purpose-gate."""

import urllib.parse
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    query = urllib.parse.parse_qs('gpc=1&purpose=analytics')
    assert query['gpc'] == ['1']
    print(json.dumps({"environment": "passed", "task_id": "232-gpc-cookie-purpose-gate"}, sort_keys=True))


if __name__ == "__main__":
    main()
