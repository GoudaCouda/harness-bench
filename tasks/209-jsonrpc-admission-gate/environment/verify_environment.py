#!/usr/bin/env python3
"""Verify the shared agent runtime for 209-jsonrpc-admission-gate."""

import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    request = dict(jsonrpc='2.0', method='notify')
    assert request['jsonrpc'] == '2.0' and 'id' not in request
    print(json.dumps({"environment": "passed", "task_id": "209-jsonrpc-admission-gate"}, sort_keys=True))


if __name__ == "__main__":
    main()
