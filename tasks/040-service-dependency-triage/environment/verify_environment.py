#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

config = {"allowed_issuers": ["internal-v1", "partner-v2"], "accepted_audiences": ["checkout"], "jwks_keys": {"partner-v2": ["k2"]}, "fail_closed": True}
cases = [
    {"issuer": "partner-v2", "audience": "checkout", "kid": "k2"},
    {"issuer": "partner-v1", "audience": "checkout", "kid": "k1"},
]
results = []
for case in cases:
    allowed = case["issuer"] in config["allowed_issuers"] and case["audience"] in config["accepted_audiences"] and case["kid"] in config["jwks_keys"].get(case["issuer"], [])
    results.append("allow" if allowed and config["fail_closed"] else "deny")
if results != ["allow", "deny"]:
    raise SystemExit(f"issuer/JWKS behavior probe failed: {results!r}")

print(json.dumps({"python3": "3.12", "json": "passed", "issuer_verifier": "passed"}, sort_keys=True))
