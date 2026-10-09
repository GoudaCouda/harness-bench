#!/usr/bin/env python3
"""Verify the shared agent runtime for 210-attestation-evidence-chain."""

import hashlib
import hmac
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    assert hmac.compare_digest(hmac.new(b'key', b'evidence', hashlib.sha256).digest(), hmac.new(b'key', b'evidence', hashlib.sha256).digest())
    print(json.dumps({"environment": "passed", "task_id": "210-attestation-evidence-chain"}, sort_keys=True))


if __name__ == "__main__":
    main()
