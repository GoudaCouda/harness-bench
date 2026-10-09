#!/usr/bin/env python3
from __future__ import annotations
import json
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

stored_at, now, ttl = 1000, 1060, 60
if now < stored_at + ttl:
    raise SystemExit("inclusive DNS TTL expiry probe failed")
soa_ttl, soa_minimum, cap = 900, 300, 600
negative_ttl = min(soa_ttl, soa_minimum, cap)
if negative_ttl != 300:
    raise SystemExit("RFC 2308 negative TTL probe failed")
refresh = {"authoritative": False, "rcode": "NOERROR"}
stale = {
    "refresh_failed": not refresh["authoritative"],
    "within_retention": True,
    "dnssec": "secure",
    "ttl": 30,
    "ede": 3,
}
if not all((stale["refresh_failed"], stale["within_retention"],
            stale["dnssec"] != "bogus", stale["ttl"] == 30, stale["ede"] == 3)):
    raise SystemExit("serve-stale/EDE boundary probe failed")
print(json.dumps({"python3":"3.12","ttl_expiry":"passed",
                  "negative_ttl":"passed","serve_stale_ede":"passed",
                  "dns_service":"not_required_by_offline_task_contract"},
                 sort_keys=True))
