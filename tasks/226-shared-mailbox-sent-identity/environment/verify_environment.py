#!/usr/bin/env python3
"""Verify the shared agent runtime for 226-shared-mailbox-sent-identity."""

import email.utils
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    address = email.utils.parseaddr('Ops <ops@example.test>')[1]
    assert address == 'ops@example.test'
    print(json.dumps({"environment": "passed", "task_id": "226-shared-mailbox-sent-identity"}, sort_keys=True))


if __name__ == "__main__":
    main()
