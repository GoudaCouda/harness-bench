#!/usr/bin/env python3
"""Verify the shared agent runtime for 233-dns-cache-zone-admission."""

import ipaddress
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    address = ipaddress.ip_address('192.0.2.8')
    assert address.version == 4 and str(address) == '192.0.2.8'
    print(json.dumps({"environment": "passed", "task_id": "233-dns-cache-zone-admission"}, sort_keys=True))


if __name__ == "__main__":
    main()
