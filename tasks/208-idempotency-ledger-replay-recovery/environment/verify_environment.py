#!/usr/bin/env python3
"""Verify the shared agent runtime for 208-idempotency-ledger-replay-recovery."""

import hashlib
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    payload = json.dumps(dict(event_id='evt-42', amount=19), sort_keys=True).encode()
    assert hashlib.sha256(payload).digest() == hashlib.sha256(payload).digest()
    print(json.dumps({"environment": "passed", "task_id": "208-idempotency-ledger-replay-recovery"}, sort_keys=True))


if __name__ == "__main__":
    main()
