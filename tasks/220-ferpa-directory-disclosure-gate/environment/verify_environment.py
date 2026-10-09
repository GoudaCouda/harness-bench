#!/usr/bin/env python3
"""Verify the shared agent runtime for 220-ferpa-directory-disclosure-gate."""

import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    record = dict(name='Ada', directory_opt_out=True)
    assert record['directory_opt_out'] is True
    print(json.dumps({"environment": "passed", "task_id": "220-ferpa-directory-disclosure-gate"}, sort_keys=True))


if __name__ == "__main__":
    main()
