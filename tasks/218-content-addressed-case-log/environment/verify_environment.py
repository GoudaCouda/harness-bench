#!/usr/bin/env python3
"""Verify the shared agent runtime for 218-content-addressed-case-log."""

import hashlib
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    assert len(hashlib.sha256(b'case-log').hexdigest()) == 64
    print(json.dumps({"environment": "passed", "task_id": "218-content-addressed-case-log"}, sort_keys=True))


if __name__ == "__main__":
    main()
