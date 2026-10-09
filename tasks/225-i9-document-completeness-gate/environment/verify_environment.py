#!/usr/bin/env python3
"""Verify the shared agent runtime for 225-i9-document-completeness-gate."""

import collections
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    docs = collections.Counter(['identity', 'employment_authorization'])
    assert all(docs[name] for name in ('identity', 'employment_authorization'))
    print(json.dumps({"environment": "passed", "task_id": "225-i9-document-completeness-gate"}, sort_keys=True))


if __name__ == "__main__":
    main()
