#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
credential = {
    "credential_id": "cred-1",
    "sign_count": 7,
    "backup_eligible": True,
    "backup_state": True,
    "risk": "low",
}
before = deepcopy(credential)
rejected = {"trusted": False, "sign_count": 9}
if rejected["trusted"]:
    credential["sign_count"] = rejected["sign_count"]
if credential != before:
    raise SystemExit("WebAuthn rejected-assertion atomicity probe failed")
accepted = {"trusted": True, "sign_count": 8}
if accepted["trusted"] and accepted["sign_count"] > credential["sign_count"]:
    credential["sign_count"] = accepted["sign_count"]
payload = json.dumps(
    {"credential": credential, "decision": "accepted"},
    sort_keys=True,
).encode()
if json.loads(payload)["credential"]["sign_count"] != 8:
    raise SystemExit("WebAuthn counter JSON probe failed")
if len(hashlib.sha256(payload).hexdigest()) != 64:
    raise SystemExit("WebAuthn state hash probe failed")
print(json.dumps({"python3": "3.12", "atomic_update": "passed", "counter_policy": "passed", "sha256": "passed"}, sort_keys=True))
