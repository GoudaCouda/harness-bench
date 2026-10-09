#!/usr/bin/env python3
from __future__ import annotations
import json
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
payload = {"ids": ["a", "b"], "policy": {"offline": True}}
encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
if json.loads(encoded) != payload:
    raise SystemExit("deterministic JSON round-trip failed")
print(json.dumps({"json": "passed", "python3": "3.12"}, sort_keys=True))
