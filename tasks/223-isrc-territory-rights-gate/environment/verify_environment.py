#!/usr/bin/env python3
"""Verify the shared agent runtime for 223-isrc-territory-rights-gate."""

import fnmatch
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    assert fnmatch.fnmatchcase('US', 'US') and not fnmatch.fnmatchcase('CA', 'US')
    print(json.dumps({"environment": "passed", "task_id": "223-isrc-territory-rights-gate"}, sort_keys=True))


if __name__ == "__main__":
    main()
