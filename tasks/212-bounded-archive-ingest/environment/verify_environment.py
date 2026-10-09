#!/usr/bin/env python3
"""Verify the shared agent runtime for 212-bounded-archive-ingest."""

import pathlib
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    member = pathlib.PurePosixPath('safe/archive.json')
    assert '..' not in member.parts and not member.is_absolute()
    print(json.dumps({"environment": "passed", "task_id": "212-bounded-archive-ingest"}, sort_keys=True))


if __name__ == "__main__":
    main()
