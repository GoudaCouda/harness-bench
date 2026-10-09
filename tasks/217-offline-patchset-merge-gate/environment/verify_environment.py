#!/usr/bin/env python3
"""Verify the shared agent runtime for 217-offline-patchset-merge-gate."""

import hashlib
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    patches = {hashlib.sha256(value).digest() for value in (b'a', b'b', b'a')}
    assert len(patches) == 2
    print(json.dumps({"environment": "passed", "task_id": "217-offline-patchset-merge-gate"}, sort_keys=True))


if __name__ == "__main__":
    main()
