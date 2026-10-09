#!/usr/bin/env python3
"""Verify the shared agent runtime for 219-dataset-manifest-pin."""

import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    manifest = dict(dataset='cases', revision='sha256:abc')
    assert manifest['revision'].startswith('sha256:')
    print(json.dumps({"environment": "passed", "task_id": "219-dataset-manifest-pin"}, sort_keys=True))


if __name__ == "__main__":
    main()
