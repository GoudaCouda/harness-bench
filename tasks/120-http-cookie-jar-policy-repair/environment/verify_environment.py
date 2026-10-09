#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import sys


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

jar = [{"name": "session", "domain": "app.example.com", "path": "/", "secure": True}]
clone = copy.deepcopy(jar)
clone[0]["name"] = "changed"
if jar[0]["name"] != "session":
    raise SystemExit("cookie input-isolation probe failed")

domain_matches = "api.example.com" == "example.com" or "api.example.com".endswith(".example.com")
path_matches = "/app/report".startswith("/app/") and not "/apple/report".startswith("/app/")
if not domain_matches or not path_matches:
    raise SystemExit("cookie domain/path scope probe failed")
if len(hashlib.sha256(b"cookie-state").hexdigest()) != 64:
    raise SystemExit("cookie state hash probe failed")

print(
    json.dumps(
        {
            "python3": "3.12",
            "deepcopy": "passed",
            "domain_scope": "passed",
            "path_scope": "passed",
            "sha256": "passed",
        },
        sort_keys=True,
    )
)
