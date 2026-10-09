#!/usr/bin/env python3
"""Verify the shared agent runtime for 216-sso-audit-token-quarantine."""

import re
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    redacted = re.sub(r'(?i)bearer\s+\S+', 'Bearer [REDACTED]', 'Bearer secret-token')
    assert redacted == 'Bearer [REDACTED]'
    print(json.dumps({"environment": "passed", "task_id": "216-sso-audit-token-quarantine"}, sort_keys=True))


if __name__ == "__main__":
    main()
